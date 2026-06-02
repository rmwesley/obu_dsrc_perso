import datetime
from pydantic import BaseModel
from fastapi import APIRouter

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

def add_gnss_fix_interpolation_to_transaction_info(transaction_with_fix_1, transaction_with_fix_2, transaction_data):
    t1 = datetime.datetime.fromisoformat(transaction_with_fix_1['creation_time']).timestamp()
    t2 = datetime.datetime.fromisoformat(transaction_with_fix_2['creation_time']).timestamp()
    timestamp = datetime.datetime.fromisoformat(transaction_data['creation_time']).timestamp()

    transaction_data['position_info'] = compute_gnss_status_position_fixes_interpolation(
        transaction_with_fix_1['position_info'], t1,
        transaction_with_fix_2['position_info'], t2,
        timestamp)

def check_gnss_status_position_presence_in_transaction_info(transaction_info) -> bool:
    return 'position_info' in transaction_info and transaction_info['position_info'] and transaction_info['position_info'] != {}

def interpolate_missing_gnss_fixes_in_transactions_list(transactions_info_list:list[dict]):
    # actual_gnss_fix_indexes = []
    prev_index = -1
    for curr_index, curr_transaction_data in enumerate(transactions_info_list):
        if check_gnss_status_position_presence_in_transaction_info(curr_transaction_data):
            for interpolation_index in range(prev_index+1, curr_index):
                if prev_index == -1:
                    continue
                add_gnss_fix_interpolation_to_transaction_info(
                    transactions_info_list[prev_index],
                    transactions_info_list[curr_index],
                    transactions_info_list[interpolation_index],
                )
            prev_index = curr_index

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

def add_gnss_fix_delta_to_transaction_info(previous_gnss_fix, current_transaction_data):
    current_transaction_data['_gnss_fix_delta'] = compute_gnss_status_position_fix_diff(previous_gnss_fix, current_transaction_data['position_info'])

def add_gnss_fix_deltas_to_transaction_list(transaction_data_list: list[dict]):
    last_position = {}
    for transaction_data in transaction_data_list:
        if 'position_info' in transaction_data and transaction_data['position_info']:
            add_gnss_fix_delta_to_transaction_info(last_position, transaction_data)
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
    transactions_info_generator = transactions_data_db_operations.get_transactions_info_for_equ_obu_id(equOBUId, skip, limit, since_dt, until_dt)

    transaction_info_list = list(transactions_info_generator)
    if interpolate_missing_gnss_fixes == True:
        interpolate_missing_gnss_fixes_in_transactions_list(transaction_info_list)
    if add_gnss_fix_deltas:
        add_gnss_fix_deltas_to_transaction_list(transaction_info_list)
    return transaction_info_list

@router.get('/pans/{personalAccountNumber}/')
async def get_transaction_info_for_pan(
    personalAccountNumber:str, skip:int=0, limit:int=20,
    since_dt:datetime.datetime=None,
    until_dt:datetime.datetime=None,
    add_gnss_fix_deltas:bool=False,
    interpolate_missing_gnss_fixes:bool=False):
    """
    Query transactions database for data related to a specific OBU ID.
    The OBU ID must be in hexadecimal format.
    """
    pan = personalAccountNumber.upper()
    transactions_info_generator = transactions_data_db_operations.get_transactions_info_for_pan(pan, skip, limit, since_dt, until_dt)

    transaction_info_list = list(transactions_info_generator)
    if interpolate_missing_gnss_fixes == True:
        interpolate_missing_gnss_fixes_in_transactions_list(transaction_info_list)
    if add_gnss_fix_deltas:
        add_gnss_fix_deltas_to_transaction_list(transaction_info_list)
    return transaction_info_list

@router.get('/transactions/{transaction_id}')
async def get_transaction_data(transaction_id:str):
    """
    Query transactions database for the data of a spefic transaction by its ID.
    """
    return transactions_data_db_operations.get_transaction_data(transaction_id)

@router.post('/sync/sync-local-files-to-remote-db')
async def sync_local_data_to_remote_db(request: SyncTransactionDataReq):
    upload_result = transactions_data_db_operations.upload_local_db_transaction_metadata_since_date(request.start_date)
    return upload_result