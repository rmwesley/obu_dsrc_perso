import pymongo
import json
import datetime
import pathlib

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

local_transactions_storage_path_str = 'local_file_storage/transactions'
local_transactions_storage_path = pathlib.Path(local_transactions_storage_path_str)

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

def get_transactions_aggregation_cursor_for_equ_obu_id(equ_obu_id:str, skip=0, limit=10):
    dsrc_transactions_db_coll = db_connect_to_transactions_coll()

    pymongo_cursor = dsrc_transactions_db_coll.aggregate([
        {'$match': {"equOBUId": equ_obu_id}},
        {'$project': {'data': 0}},
        {'$skip':  skip},
        {'$limit':  limit}
    ])
    return pymongo_cursor

def get_transactions_info_for_equ_obu_id(equ_obu_id:str, skip=0, limit=10):
    pymongo_cursor = get_transactions_aggregation_cursor_for_equ_obu_id(equ_obu_id, skip, limit)
    for transaction_data in pymongo_cursor:
        # print(transaction_data)
        yield transaction_data

def upload_local_data(size=0):
    db_transactions_collection = db_connect_to_transactions_coll()
    
    file_paths = local_transactions_storage_path.glob('*.json')
    # print(file_paths)
    for json_filename in file_paths:
        if not json_filename.endswith('.json'):
            continue
        with open(json_filename, 'r') as json_file:
            # print(json_filename)
            try:
                transaction_data = json.load(json_file)
            except json.decoder.JSONDecodeError:
                # print('Improperly encoded data!!!')
                continue
            try:
                transaction_data['_id']
            except KeyError:
                dsrc_transaction_sync_logger.debug('Transactions without _id field are obsolete!')
                # print('Transactions without _id field are obsolete!')
            mongodb_document = transaction_data
            try:
                current_transaction_id = db_transactions_collection.insert_one(document = mongodb_document)
            except pymongo.errors.DuplicateKeyError:
                dsrc_transaction_sync_logger.debug('Duplicate entry (_id field already exists)!! Please clean these files...')
                # print('Duplicate!! (Already exists)')

def upload_single_json_file(db_transactions_coll:pymongo.collection.Collection, json_filename:pathlib.Path):
    if json_filename.suffix != '.json':
        return False
    with json_filename.open('r') as json_file:
        try:
            transaction_data = json.load(json_file)
        except json.decoder.JSONDecodeError:
            dsrc_transaction_sync_logger.error('Improperly encoded JSON data!!!')
            return False
        try:
            transaction_data['_id']
        except KeyError:
            dsrc_transaction_sync_logger.error('Transactions without _id field are obsolete! Please clean these files...')
            return False
        mongodb_document = transaction_data
        try:
            current_transaction_id = db_transactions_coll.insert_one(document = mongodb_document)
        except pymongo.errors.DuplicateKeyError:
            dsrc_transaction_sync_logger.debug(f'Duplicate entry (_id field {transaction_data['_id']} already exists)!! Please clean these files...')
            return False
        dsrc_transaction_sync_logger.info(f'Data of file {json_filename} was successfully synchronized!!')
    return True

def upload_local_data_since_date(start_date:datetime.datetime) -> int:
    '''Synchronize transaction data from a start_date and then return synchronized amount (insertion_count)'''
    insertion_count = 0
    skipped_count = 0
    if type(start_date) is not datetime.datetime:
        raise TypeError("start_date should be of type datetime.datetime!!!")

    db_transactions_coll = db_connect_to_transactions_coll()
    # start_datetime_str = start_date.strftime('%Y%m%dT%H%M%S')

    file_paths = local_transactions_storage_path.glob(f'*.json')
    for json_filename in file_paths:
        modification_time_float = json_filename.stat().st_mtime
        modification_datetime = datetime.datetime.fromtimestamp(modification_time_float)

        if modification_datetime >= start_date:
            dsrc_transaction_sync_logger.debug(f'Working on {json_filename.name}...')
            result = upload_single_json_file(db_transactions_coll, json_filename)
            if result:
                insertion_count += 1
            else:
                skipped_count += 1

    return {
        'insertion_count': insertion_count,
        'skipped_count': skipped_count
    }