import pymongo
import glob
import json

import pymongo.errors

with open('settings/beacon_manager_config.json', 'r') as beacon_manager_config_file:
    beacon_manager_config = json.load(beacon_manager_config_file)

local_transactions_storage_path = 'local_file_storage/20241206_transactions'

def upload_local_data(size=0):
    print('Initializing database connection...')
    mongodb_connection_string = beacon_manager_config["database_config"]['MongoDB']['connection_string']
    mongodb_client = pymongo.MongoClient(mongodb_connection_string)

    db_name = beacon_manager_config['database_config']['MongoDB']['database_name']
    database_connection = mongodb_client[db_name]

    db_transactions_collection_name = beacon_manager_config['transaction_manager']['db_collection_name']
    db_transactions_collection = database_connection[db_transactions_collection_name]
    
    if size:
        filespaths = glob.glob(f'{local_transactions_storage_path}/*.json')[:size]
    else:
        filespaths = glob.glob(f'{local_transactions_storage_path}/*.json')
    print(filespaths)
    for json_filename in filespaths:
        if not json_filename.endswith('.json'):
            continue
        with open(json_filename, 'r') as json_file:
            print(json_filename)
            try:
                transaction_data = json.load(json_file)
            except json.decoder.JSONDecodeError:
                print('Improperly encoded data!!!')
                continue
            try:
                transaction_data['_id']
            except KeyError:
                print('Transaction without _id field are obsolete!')
            mongodb_document = transaction_data
            try:
                current_transaction_id = db_transactions_collection.insert_one(document = mongodb_document)
            except pymongo.errors.DuplicateKeyError:
                print('Duplicate!! (Already exists)')