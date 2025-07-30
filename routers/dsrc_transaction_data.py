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

def compute_gnss_status_position_fixes_interpolation(gnss_fix_1, t1, gnss_fix_2, t2, timestamp):
    gnss_fix_interpolation = {
        'interpolated': True,
        'lastGnssFixLon': int( (gnss_fix_2['lastGnssFixLon']*(timestamp-t1) + gnss_fix_1['lastGnssFixLon']*(t2-timestamp)) / (t2-t1) ),
        'lastGnssFixLat': int( (gnss_fix_2['lastGnssFixLat']*(timestamp-t1) + gnss_fix_1['lastGnssFixLat']*(t2-timestamp)) / (t2-t1) ),
        'lastGnssFixTime': int(timestamp),
    }
    return gnss_fix_interpolation

# def compute_gnss_status_position_fixes_interpolation_from_obu_times(gnss_fix_1, gnss_fix_2, timestampstamp):
#     t1 = previous_gnss_fix['lastGnssFixTime']
#     t2 = current_gnss_fix['lastGnssFixTime']
#     return compute_gnss_status_position_fixes_interpolation(gnss_fix_1, t1, gnss_fix_2, t2, timestampstamp)

def add_gnss_fix_interpolation_to_transaction_data(transaction_with_fix_1, transaction_with_fix_2, transaction_data):
    t1 = datetime.datetime.fromisoformat(transaction_with_fix_1['creation_time']).timestamp()
    t2 = datetime.datetime.fromisoformat(transaction_with_fix_2['creation_time']).timestamp()
    timestamp = datetime.datetime.fromisoformat(transaction_data['creation_time']).timestamp()

    transaction_data['position_info'] = compute_gnss_status_position_fixes_interpolation(
        transaction_with_fix_1['position_info'], t1,
        transaction_with_fix_2['position_info'], t2,
        timestamp)

def interpolate_missing_gnss_fixes_in_transactions_list(transactions_data_list:list[dict]):
    # actual_gnss_fix_indexes = []
    previous_index = 0
    for curr_index, curr_transaction_data in enumerate(transactions_data_list):
        if 'position_info' in curr_transaction_data and curr_transaction_data['position_info']:
            for interpolation_index in range(previous_index+1, curr_index):
                add_gnss_fix_interpolation_to_transaction_data(
                    transactions_data_list[previous_index],
                    transactions_data_list[curr_index],
                    transactions_data_list[interpolation_index],
                )
            previous_index = curr_index

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
async def get_transaction_info_for_obu_id(
    equOBUId:str, skip:int=0, limit:int=20,
    since_dt:datetime.datetime=None,
    until_dt:datetime.datetime=None,
    add_gnss_fix_deltas:bool=False,
    interpolate_missing_gnss_fixes:bool=False):
    """
    Query transactions database for data related to a specific OBU ID.
    The OBU ID must be in hexadecimal format.
    """
    equOBUId = equOBUId.lower()
    transactions_data_generator = transactions_data_db_operations.get_transactions_info_for_equ_obu_id(equOBUId, skip, limit, since_dt, until_dt)

    transaction_data_list = list(transactions_data_generator)
    if interpolate_missing_gnss_fixes:
        interpolate_missing_gnss_fixes_in_transactions_list(transaction_data_list)
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