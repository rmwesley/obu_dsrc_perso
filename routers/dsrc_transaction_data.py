from fastapi import APIRouter, HTTPException, Request

import datetime
from pydantic import BaseModel, Field

from typing import Literal, Optional
from enum import IntEnum

from services.db import transactions_data_db_operations

router = APIRouter(
    prefix="/data",
    tags=["DSRC Transaction Data Management Interface"])

class SyncTransactionDataReq(BaseModel):
    start_date: datetime.datetime

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "start_date": "2025-05-06T14:00:00"
                }
            ]
        }
    }

def compute_gnss_status_position_fix_diff(previous_gnss_fix, current_gnss_fix):
    if not previous_gnss_fix:
        previous_gnss_fix = current_gnss_fix
    if not current_gnss_fix:
        return

    gnss_fix_delta = {
        'gnssLonDelta': current_gnss_fix['lastGnssFixLon'] - previous_gnss_fix['lastGnssFixLon'],
        'gnssLatDelta': current_gnss_fix['lastGnssFixLat'] - previous_gnss_fix['lastGnssFixLat'],
        'gnssFixTimeDelta': current_gnss_fix['lastGnssFixTime'] - previous_gnss_fix['lastGnssFixTime'],
    }
    return gnss_fix_delta

def add_gnss_fix_delta_to_transaction_data(previous_gnss_fix, current_transaction_data):
    current_transaction_data['_gnss_fix_delta'] = compute_gnss_status_position_fix_diff(previous_gnss_fix, current_transaction_data['position_info'])

def add_gnss_fix_deltas_to_transaction_list(transaction_data_list: list[dict]):
    last_position = {}
    for transaction_data in transaction_data_list:
        if 'position_info' in transaction_data and transaction_data['position_info']:
            add_gnss_fix_delta_to_transaction_data(last_position, transaction_data)
            last_position = transaction_data['position_info']
    return transaction_data_list

@router.get('/obus/{equOBUId}/')
async def get_transaction_info_for_obu_id(equOBUId:str, skip:int=0, limit:int=20, add_gnss_fix_deltas:bool=False):
    """
    Query transactions database for data related to a specific OBU ID.
    The OBU ID must be in hexadecimal format.
    """
    equOBUId = equOBUId.lower()
    transactions_data_generator = transactions_data_db_operations.get_transactions_info_for_equ_obu_id(equOBUId, skip=skip, limit=limit)

    transaction_data_list = list(transactions_data_generator)
    if add_gnss_fix_deltas:
        add_gnss_fix_deltas_to_transaction_list(transaction_data_list)
    return transaction_data_list

@router.get('/transactions/{transaction_id}')
async def get_transaction_data(transaction_id:str):
    """
    Query transactions database for the data of a spefic transaction by its ID.
    """
    return transactions_data_db_operations.get_transaction_data(transaction_id)

@router.post('/sync/sync-local-files-to-remote-db')
async def sync_local_data_to_remote_db(request: SyncTransactionDataReq):
    upload_result = transactions_data_db_operations.upload_local_data_since_date(request.start_date)
    return upload_result