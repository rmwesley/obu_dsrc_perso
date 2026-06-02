from services.db import transactions_data_db_operations


dsrc_transactions_db_coll = transactions_data_db_operations.db_connect_to_transactions_coll()

for data in dsrc_transactions_db_coll.find({}):
    print(data['_id'])
    if 'transactionDataFileName' not in data:
        data['transactionDataFileName'] = None

    if 'RseTollDomain' in data:
        data['rseTdName'] = data['RseTollDomain']
        del data['RseTollDomain']

    if 'beaconIndividualId' not in data:
        data['beaconIndividualId'] = None

    if 'obeEquipmentClass' not in data:
        data['obeEquipmentClass'] = None

    if 'obeManufacturerId' not in data:
        data['obeManufacturerId'] = None

    if 'obeStatus' not in data:
        data['obeStatus'] = None

    if 'equOBUId' in data:
        if type(data['equOBUId']) == str and data['equOBUId']:
            data['equOBUId'] = int(data['equOBUId'], 16)

    if 'obu_provided_invalid_attr_auth_stamp' in data:
        data['authResult'] = not data['obu_provided_invalid_attr_auth_stamp']
        del data['obu_provided_invalid_attr_auth_stamp']

    if 'obu_provided_invalid_stamp' in data:
        data['authResult'] = not data['obu_provided_invalid_stamp']
        del data['obu_provided_invalid_stamp']

    if 'creation_time' in data:
        data['creation_ts'] = data['creation_time']
        del data['creation_time']

    if 'last_update_timestamp' in data:
        data['update_ts'] = data['last_update_timestamp']
        del data['last_update_timestamp']

    dsrc_transactions_db_coll.replace_one({'_id': data['_id']}, data)