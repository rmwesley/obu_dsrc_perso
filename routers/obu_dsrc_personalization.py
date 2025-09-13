from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator, field_validator
from typing import Dict, List, Literal
from enum import Enum

import json
import uuid
import pathlib
import logging
from contextlib import asynccontextmanager

from dsrc_l7 import dsrc_l7_rse
from dsrc_l7 import dsrc_perso_l7
from ASN.compiled_DSRC_instances import AXXESv1_2
import dsrc_security.kapsch_http_uset_key_obtention

obu_dsrc_perso_router_logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(arg_router: APIRouter):
    print('Initializing DSRC L7 for Perso App!!')
    try:
        await dsrc_l7_rse.init_bcm_and_set_transparent_mode()
    except Exception as e:
        print(e)
        print('Please set the beacon configuration properly to initialize it via BAC L7!')
    yield
    await dsrc_l7_rse.change_trx_mode('Stopped')

router = APIRouter(tags=['OBU DSRC Personalization routes'], lifespan=lifespan)

perso_tasks_dirpath = pathlib.Path(f'local_file_storage/dsrc_perso_tasks')

with pathlib.Path('settings/toll_domain_config.json').open('r') as json_file:
    td_conf_by_td_name = json.load(json_file)['td_conf_by_td_name']

# class dsrc_attributes_dict(Dict[int, str]):
#     pass

class ElementDsrcData(BaseModel):
    dsrc_asn1_attr_container_path: str = 'EfcDsrcGeneric.EfcContainer'
    dsrc_attributes_dict: Dict[int, str]

    @model_validator(mode='after')
    def check_attribute_ids_and_values(self):
        for attribute_id, attribute_value_hex in self.dsrc_attributes_dict.items():
            if attribute_id > 127 or attribute_id < 0:
                raise ValueError(f'Invalid Attribute Id value: {attribute_id}')
            attr_val_bytes = bytes.fromhex(attribute_value_hex)
            try:
                AXXESv1_2.EfcDsrcGeneric.EfcContainer.from_uper(attr_val_bytes)
            except AXXESv1_2.ASN1ObjErr as e:
                obu_dsrc_perso_router_logger.critical(f'Bad EFC DSRC attribute value!! Attribute {attribute_id}: 0x{attribute_value_hex}')
                raise e

        return self

class PersoTaskData(BaseModel):
    obu_model: str
    dsrc_memory_data: Dict[int, ElementDsrcData]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "obu_model": 'TRP_4010_20B_PL',
                    "dsrc_memory_data": {
                        "2": {
                            "dsrc_asn1_attr_container_path": "EfcDsrcGeneric.EfcContainer",
                            "dsrc_attributes_dict": {
                                "17": "3150",
                                "18": "32000000",
                                "19": "33005D",
                                "20": "340C800FA00000",
                                "22": "3620000024"
                            }
                        }
                    }
                },
                {
                    "obu_model": "TRP_4010_20B_PL",
                    "dsrc_memory_data": {
                        "0": {
                        "dsrc_attributes_dict": {
                            "33": "02020301"
                        },
                        "dsrc_asn1_attr_container_path": "EfcDsrcGeneric.EfcContainer"
                        },
                        "2": {
                        "dsrc_attributes_dict": {},
                        "dsrc_asn1_attr_container_path": "EfcDsrcGeneric.EfcContainer"
                        }
                    }
                },
                {
                    "obu_model": 'TRP_4010_20B_PL',
                    "dsrc_memory_data": {
                        "2": {
                            "dsrc_asn1_attr_container_path": "EfcDsrcGeneric.EfcContainer",
                            "dsrc_attributes_dict": {
                                "17": "3151",
                                "18": "32000000",
                                "19": "33001A",
                                "20": "34070811300000",
                                "22": "3660000024"
                            }
                        }
                    }
                }
            ]
        }
    }

@router.post('/persos/')
def create_personalization_task(perso_task_data:PersoTaskData):
    perso_id = uuid.uuid4()
    perso_data_filepath = perso_tasks_dirpath / f'{perso_id}.json'

    with perso_data_filepath.open('w') as json_file:
        json_file.write(perso_task_data.model_dump_json(indent=2))

    return {
        'message': 'Personalization Request received!',
        'perso_id': perso_id
    }

class PersoTaskState(str, Enum):
    PENDING = 'pending'
    FINISHED = 'finished'

@router.get('/persos')
def get_orders(perso_state:PersoTaskState) -> list:
    return []

@router.get('/persos/state/{perso_state}')
def get_orders(perso_state:PersoTaskState) -> list:
    return []

class PersonalizationError(Exception):
    pass

def get_perso_data(perso_id: str) -> PersoTaskData:
    perso_data_filepath = perso_tasks_dirpath / f'{perso_id}.json'

    with perso_data_filepath.open('r') as json_file:
        json_str = json_file.read()
        perso_task_data = PersoTaskData.model_validate_json(json_str)
    return perso_task_data

@router.post('/persos/{perso_id}/kapsch_dsrc_uset_perso_apply/')
async def apply_kapsch_personalization_data_to_obu(perso_id:str, uset_key_type:str = 'Stock'):
    '''Request application of personalization to OBU through a DSRC beacon'''

    perso_task_data = get_perso_data(perso_id)

    dsrc_memory_data = {eid: el_dsrc_data.dsrc_attributes_dict for eid, el_dsrc_data in perso_task_data.dsrc_memory_data.items()}
    obu_id_hex = await dsrc_perso_l7.kapsch_trp_4010_20b_pl_perso(
        obu_model = perso_task_data['obu_model'],
        dsrc_memory_data = dsrc_memory_data,
        uset_key_type = uset_key_type
        )

    return {
        'equOBUId_hex': obu_id_hex
    }

class PersoValidationError(Exception):
    pass

@router.post('/persos/{perso_id}/validation')
def validate_obu_data_and_finish_perso(perso_id:str):
    '''Validate that an OBU was personalized properly.
    In a proper SupplyChain process, the personalization request's state must be PENDING, not FINISHED!'''
    try:
        obu_id = bytes(8)
        obu_id_hex = obu_id.hex().upper()
        perso_state = 'finished'
        return f'Personalization validated for OBU ID 0x{obu_id_hex}!'
    except:
        raise PersoValidationError(f'OBU with ID 0x{obu_id_hex} was not personalized with perso_id ({perso_id})!')
    pass

# with pathlib.Path('local_file_storage/valid_obu_models_by_td.json').open('r') as json_file:
#     valid_obu_models_by_td = json.load(json_file)

# @router.get('/valid_obu_contract_refs')
# def get_valid_obu_contracts(td_name:str|None = None):
#     if td_name is None:
#         return valid_obu_models_by_td
#     elif td_name in valid_obu_models_by_td:
#         return valid_obu_models_by_td[td_name]
#     else:
#         raise HTTPException(400, f'Invalid Toll Domain Name: ({td_name})')

# def validate_efc_toll_domain_dsrc_data(tollDomain: str, dsrc_attributes_dict:dsrc_attributes_dict):
#     for attribute_id, attribute_value in dsrc_attributes_dict.items():
#         try:
#             # Validate attribute value against EfcContainer!
#             attributeValueUper = bytes.fromhex(attribute_value)
#             attribute_value = AXXESv1_2.EfcDsrcGeneric.EfcContainer.from_uper(attributeValueUper)
#         except ASN1ObjErr:
#             raise Exception(f'Invalid Attribute value (0x{attribute_value})! It should be a UPER-encoded Hex string representing an ISO14906 EfcContainer ASN1 value!')

@router.post('/kapsch_dsrc_uset_perso_apply/')
async def apply_kapsch_personalization_data_to_obu(perso_task_data:PersoTaskData, uset_key_type:str = 'Stock'):
    '''Request application of personalization to OBU through a DSRC beacon'''
    try:
        await dsrc_l7_rse.check_and_update_beacon_state()
    except dsrc_l7_rse.NoBeaconInitialized as e:
        raise HTTPException(409, detail=str(e))

    dsrc_memory_data = {eid: el_dsrc_data.dsrc_attributes_dict for eid, el_dsrc_data in perso_task_data.dsrc_memory_data.items()}
    obu_id_hex = await dsrc_perso_l7.kapsch_trp_4010_20b_pl_perso(
        obu_model = perso_task_data['obu_model'],
        dsrc_memory_data = dsrc_memory_data,
        uset_key_type = uset_key_type
        )

    return {
        'equOBUId_hex': obu_id_hex
    }

class UsetSwitchPayload(BaseModel):
    obu_model: str
    current_uset_key_type: str
    new_uset_key_type: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "obu_model": "TRP_4010_20B_PL",
                    "current_uset_key_type": "Stock",
                    "new_uset_key_type": "Exploit"
                }
            ]
        }
    }

@router.post('/kapsch_dsrc_switch_uset_keys/')
async def switch_kapsch_obu_uset_keys(req_body: UsetSwitchPayload):
    '''Switch OBU USET keys for all EIDs!'''

    obu_id_hex = await dsrc_perso_l7.kapsch_switch_uset_keys(
        obu_model = req_body.obu_model,
        curr_uset_key_type = req_body.current_uset_key_type,
        new_uset_key_type = req_body.new_uset_key_type
        )

    return {
        'equOBUId_hex': obu_id_hex
    }

@router.post('/kapsch_dsrc_force_uset_keys/')
async def force_kapsch_obu_uset_keys(req_body: UsetSwitchPayload):
    '''Try to switch OBU USET keys for all EIDs, ignoring AccessDenied errors!'''

    try:
        try:
            obu_id_hex = await dsrc_perso_l7.kapsch_force_uset_key(
                obu_model = req_body.obu_model,
                curr_uset_key_type = req_body.current_uset_key_type,
                new_uset_key_type = req_body.new_uset_key_type
                )
        except dsrc_l7_rse.UnclosedTransactionException as e:
            raise HTTPException(502, detail=str(e))

    except dsrc_security.kapsch_http_uset_key_obtention.KapschHttpWsError as e:
        raise HTTPException(502, detail={
            "cause": "Kapsch HTTP USET computation service is unavailable!!",
            "error_message": str(e),
            })

    return {
        'equOBUId_hex': obu_id_hex
    }

@router.post('/kapsch_dsrc_force_uset_keys/')
async def force_kapsch_obu_uset_keys(req_body: UsetForcePayload):
    '''Request application of personalization to OBU through a DSRC beacon'''

    obu_id_hex = await dsrc_perso_l7.kapsch_force_uset_key(
        obu_model = req_body.obu_model,
        new_uset_key_type = req_body.new_uset_key_type
        )

    return {
        'equOBUId_hex': obu_id_hex
    }

class PersonalizeAndSwitchUsetKeys(BaseModel):
    perso_task_data: PersoTaskData
    current_uset_key_type: str
    new_uset_key_type: str

@router.post('/kapsch_dsrc_uset_perso_apply_and_switch_uset_keys/')
async def apply_kapsch_personalization_data_to_obu_and_switch_uset_keys(req_body:PersonalizeAndSwitchUsetKeys):
    '''Request application of personalization to OBU through a DSRC beacon'''
    obu_id_hex = apply_kapsch_personalization_data_to_obu(req_body.perso_task_data, req_body.current_uset_key_type)
    switch_kapsch_obu_uset_keys()

    second_obu_id_hex = await dsrc_perso_l7.kapsch_switch_uset_keys(
        obu_model = req_body.perso_task_data.obu_model,
        curr_uset_key_type = req_body.current_uset_key_type,
        new_uset_key_type = req_body.new_uset_key_type
        )
    if obu_id_hex != second_obu_id_hex:
        raise HTTPException(status_code=409, detail='OBU ID changed during personalization procedure!!')

    return {
        'equOBUId_hex': obu_id_hex
    }