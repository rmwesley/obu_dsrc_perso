from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator, field_validator
from typing import Dict, List
from enum import Enum

import json
import uuid
import pathlib

from pycrate.pycrate_asn1c.err import ASN1ObjErr
from ASN.compiled_DSRC_instances import AXXESv1_2

router = APIRouter(tags=['OBU Personalization routes'])

perso_tasks_dirpath = pathlib.Path(f'local_file_storage/perso_tasks')

with pathlib.Path('local_file_storage/valid_obu_models_by_td.json').open('r') as json_file:
    valid_obu_models_by_td = json.load(json_file)

@router.get('/valid_obu_contract_refs')
def get_valid_obu_contracts(td_name:str|None = None):
    if td_name is None:
        return valid_obu_models_by_td
    elif td_name in valid_obu_models_by_td:
        return valid_obu_models_by_td[td_name]
    else:
        raise HTTPException(400, f'Invalid Toll Domain Name: ({td_name})')

with pathlib.Path('settings/toll_domain_config.json').open('r') as json_file:
    td_conf_by_td_name = json.load(json_file)['td_conf_by_td_name']

class DsrcAttributesDict(BaseModel):
    @model_validator(mode='after')
    def check_attribute_ids(cls, dsrc_attributes_dict):
        for attribute_id in dsrc_attributes_dict:
            if attribute_id > 127 or attribute_id < 0:
                raise AssertionError(f'Invalid Attribute Id value: {attribute_id}')
        return dsrc_attributes_dict

class TollDomainPersoData(BaseModel):
    tollDomain: str
    dsrcAttributesDict: dict

    @field_validator('tollDomain',mode='after')
    def check_toll_domain_name(cls, toll_domain_name):
        if toll_domain_name not in valid_obu_models_by_td or toll_domain_name not in td_conf_by_td_name:
            raise AssertionError(f'Invalid Toll Domain: ({toll_domain_name})')
        return toll_domain_name

class InvalidObuModelContractRef(Exception):
    pass

class PersoTaskData(BaseModel):
    obuModelRef: str
    dsrcMemoryData: List[TollDomainPersoData]

    @model_validator(mode='after')
    def check_obu_model_contracts_for_each_td(cls, values):
        for td_perso_data in values.dsrcMemoryData:
            toll_domain_name = td_perso_data.tollDomain
            valid_obus = valid_obu_models_by_td[toll_domain_name]

            if values.obuModelRef not in valid_obus:
                raise InvalidObuModelContractRef(f'The OBU model contract reference (0x{values.obuModelRef}) is not supported by the Toll Domain ({toll_domain_name})!!')
        return values

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "obuModelRef": '00075113',
                    "dsrcMemoryData": [
                        {
                            'tollDomain': 'EasyGo',
                            'dsrcAttributesDict': {0: '20B2803100066F'}
                        },
                        {
                            'tollDomain': 'CH',
                            'dsrcAttributesDict': {0: '20B2803100066F'}
                        }
                    ]
                }
            ]
        }
    }

def validate_efc_toll_domain_dsrc_data(tollDomain: str, dsrcAttributesDict:DsrcAttributesDict):
    for attribute_id, attribute_value in dsrcAttributesDict.items():
        try:
            # Validate attribute value against EfcContainer!
            attributeValueUper = bytes.fromhex(attribute_value)
            attribute_value = AXXESv1_2.EfcDsrcGeneric.EfcContainer.from_uper(attributeValueUper)
        except ASN1ObjErr:
            raise Exception(f'Invalid Attribute value (0x{attribute_value})! It should be a UPER-encoded Hex string representing an ISO14906 EfcContainer ASN1 value!')

def validate_ccc_toll_domain_dsrc_data(tollDomain: str, dsrcAttributesDict:DsrcAttributesDict):
    for attribute_id, attribute_value in dsrcAttributesDict.items():
        try:
            # Validate attribute value against CccContainer!
            attributeValueUper = bytes.fromhex(attribute_value)
            attribute_value = AXXESv1_2.EfcCcc.CccContainer.from_uper(attributeValueUper)
        except ASN1ObjErr:
            raise Exception(f'Invalid Attribute value (0x{attribute_value})! It should be a UPER-encoded Hex string representing an ISO14906 EfcContainer ASN1 value!')

def validate_dsrc_data(tollDomain: str, dsrcAttributesDict:DsrcAttributesDict):
    if 1 in td_conf_by_td_name[tollDomain]['mandApplications']:
        validate_efc_toll_domain_dsrc_data(tollDomain, dsrcAttributesDict)
    if 20 in td_conf_by_td_name[tollDomain]['mandApplications']:
        validate_ccc_toll_domain_dsrc_data(tollDomain, dsrcAttributesDict)

@router.post('/persos/')
def create_personalization_task(perso_task_data:PersoTaskData):
    for tollDomainPersoData in perso_task_data.dsrcMemoryData:
        tollDomain = tollDomainPersoData.tollDomain
        dsrcAttributesDict = tollDomainPersoData.dsrcAttributesDict

        validate_dsrc_data(tollDomain, dsrcAttributesDict)

    perso_id = uuid.uuid4()
    perso_data_filepath = perso_tasks_dirpath / f'{perso_id}.json'

    with perso_data_filepath.open('w') as json_file:
        json_file.write(perso_task_data.model_dump_json(indent=2))

    return {
        'message': 'Personalization Request received!',
        'perso_id': perso_id
    }

class PersoRequestState(str, Enum):
    PENDING = 'pending'
    FINISHED = 'finished'

@router.get('/persos')
def get_orders(perso_state:PersoRequestState) -> list:
    return []

@router.get('/persos/state/{perso_state}')
def get_orders(perso_state:PersoRequestState) -> list:
    return []

class PersoApplicationMethod(str, Enum):
    DSRC = 'table_dsrc_beacon'
    AXXES = 'axxes_dm'

class PersonalizationError(Exception):
    pass

@router.post('/persos/{perso_id}')
def apply_personalization_data_to_obu(perso_state:PersoRequestState, perso_id:str, method:PersoApplicationMethod):
    '''Request application of personalization to OBU via Proxy or via a DSRC beacon'''

    try:
        obu_id: bytes(8)
        obu_id_hex = obu_id.hex().upper()
        return f'Personalization successful for OBU ID 0x{obu_id_hex}!'
    except:
        raise PersonalizationError(f'Personalization for {perso_id} was unsuccessful!')

class PersoValidationMethod(str, Enum):
    DSRC = 'table_dsrc_beacon'
    AXXES_DB = 'axxes_dm_db_query'
    AXXES_API = 'axxes_dm_http_api'

class PersoValidationError(Exception):
    pass

@router.post('/persos/{perso_id}')
def validate_obu_data_and_finish_perso(perso_id:str, method: PersoValidationMethod):
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