import pymongo
import json
import datetime

from dsrc_transactions.metadata_persistence import TransactionMetadataHandler
import pymongo.collection
import pymongo.errors

import logging

dsrc_transaction_sync_logger = logging.getLogger(__name__)
dsrc_transaction_sync_logger.setLevel(logging.DEBUG)

startup_date = datetime.datetime.now()
logs_date_prefix = startup_date.strftime('%y%m%d')

# SETTING UP LOGGER FILE HANDLER
file_handler = logging.FileHandler(f'logs/proxy_client_logs/{logs_date_prefix}_transactions_data_sync.log')
file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)
dsrc_transaction_sync_logger.addHandler(file_handler)

with open('settings/beacon_proxy_config.json', 'r') as json_file:
    beacon_proxy_config = json.load(json_file)
    mongodb_config = beacon_proxy_config["mongodb_config"]

def db_connect_to_transactions_coll() -> pymongo.collection.Collection:
    global dsrc_transactions_db_coll

    if 'dsrc_transactions_db_coll' in globals():
        return dsrc_transactions_db_coll

    dsrc_transaction_sync_logger.info('Connection to (dsrc_transactions) collection of (bm_db) MongoDB database...')
    mongodb_connection_string = mongodb_config['connection_string']
    mongodb_client = pymongo.MongoClient(mongodb_connection_string)

    db_name = mongodb_config['database_name']
    database_connection = mongodb_client[db_name]

    dsrc_transactions_db_coll = database_connection['dsrc_transactions']
    return dsrc_transactions_db_coll

def get_transaction_data(transaction_id:str):
    dsrc_transactions_db_coll = db_connect_to_transactions_coll()
    return dsrc_transactions_db_coll.find_one({'_id': transaction_id})

def get_transactions_info_aggregation_cursor_for_equ_obu_id(equ_obu_id:str, skip=0, limit=20, since_dt_str:str='', until_dt_str:str='9'):
    dsrc_transactions_db_coll = db_connect_to_transactions_coll()

    # print('Since:', since_dt_str)
    pymongo_cursor = dsrc_transactions_db_coll.aggregate([
        {'$match': {
            "equOBUId": equ_obu_id,
            "creation_time": {
                '$gte': since_dt_str,
                '$lte': until_dt_str,
                },
            }},
        {'$project': {'data': 0}},
        {'$sort': {'creation_time': -1}},
        {'$skip':  skip},
        {'$limit':  limit},
    ])
    return pymongo_cursor

def get_transactions_info_aggregation_cursor_for_pan(pan:str, skip=0, limit=20, since_dt_str:str='', until_dt_str:str='9'):
    dsrc_transactions_db_coll = db_connect_to_transactions_coll()

    # print('Since:', since_dt_str)
    pymongo_cursor = dsrc_transactions_db_coll.aggregate([
        {'$match': {
            "personalAccountNumber": pan,
            "creation_time": {
                '$gte': since_dt_str,
                '$lte': until_dt_str,
                },
            }},
        {'$project': {'data': 0}},
        {'$sort': {'creation_time': -1}},
        {'$skip':  skip},
        {'$limit':  limit},
    ])
    return pymongo_cursor

def get_transactions_info_for_equ_obu_id(equ_obu_id:str, skip=0, limit=20, since_dt:datetime.datetime=None, until_dt:datetime.datetime=None):
    since_dt_str = since_dt.isoformat() if type(since_dt) is datetime.datetime else ''
    until_dt_str = until_dt.isoformat() if type(until_dt) is datetime.datetime else '9'

    # since_dt_str = since_dt.strftime('%Y-%M-%dT%H:%M:%S.')
    # until_dt_str = until_dt.isoformat()
    pymongo_cursor = get_transactions_info_aggregation_cursor_for_equ_obu_id(equ_obu_id, skip, limit, since_dt_str, until_dt_str)
    for transaction_info in pymongo_cursor:
        # print(transaction_data)
        yield transaction_info

def get_transactions_info_for_pan(pan:str, skip=0, limit=20, since_dt:datetime.datetime=None, until_dt:datetime.datetime=None):
    since_dt_str = since_dt.isoformat() if type(since_dt) is datetime.datetime else ''
    until_dt_str = until_dt.isoformat() if type(until_dt) is datetime.datetime else '9'

    # since_dt_str = since_dt.strftime('%Y-%M-%dT%H:%M:%S.')
    # until_dt_str = until_dt.isoformat()
    pymongo_cursor = get_transactions_info_aggregation_cursor_for_pan(pan, skip, limit, since_dt_str, until_dt_str)
    for transaction_info in pymongo_cursor:
        # print(transaction_data)
        yield transaction_info

# def get_transactions_info_for_equ_obu_id(equ_obu_id:str, skip=0, limit=20, add_displacements:bool=True):
#     pymongo_cursor = get_transactions_aggregation_cursor_for_equ_obu_id(equ_obu_id, skip, limit)
#     last_position = {}
#     for transaction_data in pymongo_cursor:
#         if 'position_info' in transaction_data and transaction_data['position_info']:
#             if add_displacements:
#                 add_gnss_fix_delta_to_transaction_data(last_position, transaction_data)
#             last_position = transaction_data['position_info']
#         yield transaction_data

# def get_transactions_info_for_equ_obu_id_and_interpolate_when_necessary(equ_obu_id:str, skip=0, limit=20):
#     pymongo_cursor = get_transactions_aggregation_cursor_for_equ_obu_id(equ_obu_id, skip, limit)
#     last_position = {}
#     for transaction_data in pymongo_cursor:
#         if 'position_info' in transaction_data and transaction_data['position_info']:
#             last_position = transaction_data['position_info']
#             # print(last_position)
#         else:
#             transaction_data['position_info'] = last_position
#         yield transaction_data

def upload_transaction_metadata(db_transactions_coll:pymongo.collection.Collection, transaction_metadata) -> bool:
    try:
        transaction_metadata['transactionUuid']
    except KeyError:
        dsrc_transaction_sync_logger.error('Rows without a (transactionUuid) field are obsolete! Please clean these rows...')
        return False
    mongodb_document = dict(transaction_metadata)

    # Rename (transactionUuid) as (_id) for MongoDB
    mongodb_document['_id'] = transaction_metadata['transactionUuid']
    del mongodb_document['id'] # Remove SQLite's (id) field
    del mongodb_document['transactionUuid']

    try:
        db_transactions_coll.insert_one(document = mongodb_document)
    except pymongo.errors.DuplicateKeyError:
        dsrc_transaction_sync_logger.error(f'Duplicate entry (_id) for ({mongodb_document["_id"]})!! Please clean these rows...')
        return False
    dsrc_transaction_sync_logger.info(f'Metadata for transaction {mongodb_document["_id"]} was successfully synchronized!!')
    return True

def upload_local_db_transaction_metadata_since_date(start_date:datetime.datetime) -> int:
    '''Synchronize local transaction metadata from a start_date and then return synchronized amount (insertion_count)'''
    insertion_count = 0
    skipped_count = 0
    if type(start_date) is not datetime.datetime:
        raise TypeError("start_date should be of type datetime.datetime!!!")

    db_transactions_coll = db_connect_to_transactions_coll()
    # start_datetime_str = start_date.strftime('%Y%m%dT%H%M%S')

    transaction_metadata_handler = TransactionMetadataHandler()
    metadata_cursor = transaction_metadata_handler.get_transactions_metadata_since_date_dict_iter(since_date=start_date)
    for transaction_metadata in metadata_cursor:
        dsrc_transaction_sync_logger.debug(f'Working on {transaction_metadata}...')
        result = upload_transaction_metadata(db_transactions_coll, transaction_metadata)
        if result:
            insertion_count += 1
        else:
            skipped_count += 1

    return {
        'insertion_count': insertion_count,
        'skipped_count': skipped_count
    }