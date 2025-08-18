from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator, field_validator
from typing import Dict, List, Literal
from enum import Enum

import json
import uuid
import pathlib

from dsrc_l7 import dsrc_perso_l7
from pycrate.pycrate_asn1c.err import ASN1ObjErr
from ASN.compiled_DSRC_instances import AXXESv1_2

router = APIRouter(tags=['OBU DSRC Personalization routes'])

perso_tasks_dirpath = pathlib.Path(f'local_file_storage/dsrc_perso_tasks')

with pathlib.Path('settings/toll_domain_config.json').open('r') as json_file:
    td_conf_by_td_name = json.load(json_file)['td_conf_by_td_name']

class DsrcAttributesDict(BaseModel):
    @model_validator(mode='after')
    def check_attribute_ids(cls, dsrc_attributes_dict):
        for attribute_id in dsrc_attributes_dict:
            if attribute_id > 127 or attribute_id < 0:
                raise AssertionError(f'Invalid Attribute Id value: {attribute_id}')
        return dsrc_attributes_dict

class ElementDsrcData(BaseModel):
    dsrc_asn1_attr_container_path: str = 'EfcDsrcGeneric.EfcContainer'
    dsrcAttributesDict: dict

class InvalidObuModelContractRef(Exception):
    pass

class PersoTaskData(BaseModel):
    obuModelRef: str
    dsrcMemoryData: Dict[int, ElementDsrcData]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "obuModelRef": '00075113',
                    "dsrcMemoryData": {
                        "4": {
                            "dsrc_asn1_attr_container_path": "EfcDsrcGeneric.EfcContainer",
                            "dsrcAttributesDict": {
                                "17": "3120",
                                "18": "32202020",
                                "19": "332020",
                                "20": "34202020202020",
                                "21": "352020",
                                "22": "3620202020"
                                }
                        },
                        "7": {
                            "dsrc_asn1_attr_container_path": "EfcDsrcGeneric.EfcContainer",
                            "dsrcAttributesDict": {
                                "17": "3120",
                                "18": "32202020",
                                "19": "332020",
                                "20": "34202020202020",
                                "21": "352020",
                                "22": "3620202020"
                                }
                        }
                    }
                }
            ]
        }
    }

@router.post('/persos/')
def create_personalization_task(perso_task_data:PersoTaskData):
    for eid, elementDsrcData in perso_task_data.dsrcMemoryData.items():
        dsrcAttributesDict = elementDsrcData.dsrcAttributesDict
        # validate_efc_toll_domain_dsrc_data(tollDomain, dsrcAttributesDict)

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
        perso_task_data = PersoTaskData.parse_file(json_file)
    return perso_task_data

# PersoMethods = Literal['TRP_4010_20B_USET']
# async def apply_personalization_data_to_obu(perso_state:PersoTaskState, perso_id:str, perso_method: PersoMethods):
@router.post('/persos/{perso_id}')
async def apply_personalization_data_to_obu(perso_state:PersoTaskState, perso_id:str):
    '''Request application of personalization to OBU through a DSRC beacon'''

    perso_task_data = get_perso_data(perso_id)
    for eid, element_dsrc_data in perso_task_data.items():
        element_dsrc_data
    await dsrc_perso_l7.kapsch_tsp_4010_20b_pl_perso()
    try:
        obu_id: bytes(8)
        obu_id_hex = obu_id.hex().upper()
        return f'Personalization successful for OBU ID 0x{obu_id_hex}!'
    except:
        raise PersonalizationError(f'Personalization for {perso_id} was unsuccessful!')

class PersoValidationError(Exception):
    pass

@router.post('/persos/{perso_id}/validation')
def validate_obu_data_and_finish_perso(perso_id:str):
    '''Validate that an OBU was personalized properly.
    In a proper SupplyChain process, the personalization request's state must be PENDING, not FINISHED!'''
    try:
        obu_id: bytes(8)
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

# def validate_efc_toll_domain_dsrc_data(tollDomain: str, dsrcAttributesDict:DsrcAttributesDict):
#     for attribute_id, attribute_value in dsrcAttributesDict.items():
#         try:
#             # Validate attribute value against EfcContainer!
#             attributeValueUper = bytes.fromhex(attribute_value)
#             attribute_value = AXXESv1_2.EfcDsrcGeneric.EfcContainer.from_uper(attributeValueUper)
#         except ASN1ObjErr:
#             raise Exception(f'Invalid Attribute value (0x{attribute_value})! It should be a UPER-encoded Hex string representing an ISO14906 EfcContainer ASN1 value!')