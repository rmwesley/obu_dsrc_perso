from fastapi import APIRouter
from enum import Enum

router = APIRouter(tags=['OBU Personalization routes'])

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