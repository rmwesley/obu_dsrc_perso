from fastapi import APIRouter, HTTPException
from enum import Enum

import json
import pathlib

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