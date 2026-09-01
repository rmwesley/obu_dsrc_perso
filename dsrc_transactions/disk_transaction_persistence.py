import json
import datetime
import logging
import uuid_extensions

from custom_its_decoders import custom_its_per_decoders

from .db_metadata_persistence import TransactionMetadataHandler
from ..toll_charging_security import tc_manage_toll_domains
from ..globals import BASE_DIR, LOG_DIR

# File logger, so prevent propagation!!
disk_persist_logger = logging.getLogger(__name__)
disk_persist_logger.setLevel(logging.INFO)
disk_persist_logger.propagate = False

startup_date = datetime.datetime.now()
logs_date_prefix = startup_date.strftime('%y%m%d')

# SETTING UP LOGGER FILE HANDLER
transaction_logs_path = LOG_DIR / f'beacon_logs/{logs_date_prefix}_transactions_persistance.log'
transaction_logs_path.parent.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(transaction_logs_path)
file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)
disk_persist_logger.addHandler(file_handler)

transactions_stg_path = BASE_DIR / 'local_file_storage/transactions'

def create_transaction_data_file_from_init_phase_data(initialization_request_jval, initialization_response_jval):
    transaction_uuid = uuid_extensions.uuid7(as_type='str')

    current_td = tc_manage_toll_domains.get_current_toll_domain()

    # initialization_data dict is a merge of the init request and response JSON values
    # initialization_data = initialization_request_jval | initialization_response_jval
    initialization_data = {}
    # Merging initialisationRequest json into initialization_data json dict
    initialization_data |= initialization_request_jval
    # Merging initialisationResponse json into initialization_data json dict
    initialization_data |= initialization_response_jval

    obeManufacturerID = initialization_data['initialisationResponse']['obeConfiguration']['manufacturerID']
    obeEquipmentClass = initialization_data['initialisationResponse']['obeConfiguration']['equipmentClass']
    # equOBUId = 0

    # Actual data at the bottom!
    transaction_data_body = {}
    transaction_data_body['initialization_phase'] = initialization_data
    # Create an empty list for future data exchanges (ACTION/GET/SET requests...)
    transaction_data_body['transaction_phase'] = []

    current_transaction_start_date = datetime.datetime.now()
    current_transaction_datetime_prefix = current_transaction_start_date.strftime("%Y%m%dT%H%M%S")

    transaction_data_filename = f"{current_transaction_datetime_prefix}_{current_td}_{obeManufacturerID:04X}_{obeEquipmentClass:04X}_{transaction_uuid}.json"
    filepath = transactions_stg_path / transaction_data_filename

    metadata_handler = TransactionMetadataHandler()
    metadata_handler.create_transaction_with_init_data(current_td, initialization_request_jval, initialization_response_jval, filepath.name, transaction_uuid)

    with filepath.open('w') as json_file:
        transaction_data = {}
        transaction_data['data'] = transaction_data_body
        json.dump(transaction_data, json_file, indent=2)

    return transaction_data_filename, transaction_uuid, initialization_data

def search_json_action_transaction_data_for_attribute_data(action_request_jval, action_response_jval, attribute_id:int):
    if 'actionParameter' in action_request_jval:
        if 'gstrq' in action_request_jval['actionParameter']:
            if attribute_id in action_request_jval['actionParameter']['gstrq']['attributeIdList']:
                try:
                    for attribute_data in action_response_jval['responseParameter']['gstrs']['attributeList']:
                        if attribute_data['attributeId'] == attribute_id:
                            return attribute_data['attributeValue']
                except KeyError:
                    disk_persist_logger.error(f'ACTION response does not contain data for Attribute Id ({attribute_id})!!')
                    return {}
    return {}

def search_json_get_transaction_data_for_attribute_data(get_request_jval, get_response_jval, attribute_id:int):
    if attribute_id in get_request_jval['attrIdList']:
        try:
            for attribute_data in get_response_jval['attributelist']:
                if attribute_data['attributeId'] == attribute_id:
                    return attribute_data['attributeValue']
        except KeyError:
            disk_persist_logger.error(f'GET response does not contain data for Attribute Id ({attribute_id})!!')
            return {}
    return {}

def search_json_t_apdu_exchange_data_for_attribute_value(request_t_apdu_jval, response_t_apdu_jval, attribute_id:int):
    if 'actionRequest' in request_t_apdu_jval:
        action_req_jval = request_t_apdu_jval['actionRequest']
        action_resp_jval = response_t_apdu_jval['actionResponse']

        attribute_value = search_json_action_transaction_data_for_attribute_data(action_req_jval, action_resp_jval, attribute_id)
        return attribute_value

    if 'getRequest' in request_t_apdu_jval:
        get_req_jval = request_t_apdu_jval['getRequest']
        get_resp_jval = response_t_apdu_jval['getResponse']

        attribute_value = search_json_get_transaction_data_for_attribute_data(get_req_jval, get_resp_jval, attribute_id)
        return attribute_value
    return {}

def search_for_obu_id_value_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval):
    attribute_value = search_json_t_apdu_exchange_data_for_attribute_value(request_t_apdu_jval, response_t_apdu_jval, attribute_id=24)
    if 'equOBUId' in attribute_value:
        equOBUId_hex = attribute_value['equOBUId'].upper()
        return equOBUId_hex

def search_for_pan_value_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval):
    attribute_value = search_json_t_apdu_exchange_data_for_attribute_value(request_t_apdu_jval, response_t_apdu_jval, attribute_id=32)

    if 'paymeans' in attribute_value:
        personalAccountNumber = attribute_value['paymeans']['personalAccountNumber'].upper()
        return personalAccountNumber

def search_for_lpn_data_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval):
    attribute_value = search_json_t_apdu_exchange_data_for_attribute_value(request_t_apdu_jval, response_t_apdu_jval, attribute_id=16)

    if 'vehlpn' in attribute_value:
        lpn_country_code = attribute_value['vehlpn']['countryCode']
        lpn = attribute_value['vehlpn']['licencePlateNumber'].upper()
        return lpn_country_code, lpn
    return None, None

def search_for_gnss_status_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval):
    attribute_value = search_json_t_apdu_exchange_data_for_attribute_value(request_t_apdu_jval, response_t_apdu_jval, attribute_id=50)

    if 'gnssStatus' in attribute_value:
        return attribute_value['gnssStatus']

def get_transaction_data_header_updates(request_t_apdu_jval, response_t_apdu_jval, obe_auth:bool):
    metadata_updates = []

    equOBUId_hex = search_for_obu_id_value_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval)
    equOBUId_int = int(equOBUId_hex, 16) if equOBUId_hex else None
    metadata_updates.append(equOBUId_int)

    pan_hex = search_for_pan_value_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval) or None
    metadata_updates.append(pan_hex)

    lpn_country_code_hex, lpn_hex = search_for_lpn_data_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval)
    if lpn_country_code_hex is not None:
        lpn_country_code_alpha2 = custom_its_per_decoders.decode_baudot_country_code(lpn_country_code_hex)
    else:
        lpn_country_code_alpha2 = None
    metadata_updates.append(lpn_country_code_alpha2)
    metadata_updates.append(lpn_hex)

    gnss_status = search_for_gnss_status_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval) or {}

    metadata_updates.append(gnss_status.get('lastGnssFixLat', None))
    metadata_updates.append(gnss_status.get('lastGnssFixLon', None))
    metadata_updates.append(gnss_status.get('lastGnssFixTime', None))
    metadata_updates.append(gnss_status.get('currentHdop', {}).get('hDop', None))
    metadata_updates.append(gnss_status.get('currentHdop', {}).get('numberOfUsedSatellites', None))

    metadata_updates.append(obe_auth)

    return metadata_updates

def add_t_apdu_data_to_transaction_data(transaction_uuid:str, transaction_data_filename:str, request_t_apdu_jval, response_t_apdu_jval, obe_auth:bool):
    # new_transaction_phase_data_json dict is a merge of the T-APDU request and response JSON values
    new_transaction_phase_data_json = request_t_apdu_jval | response_t_apdu_jval

    filepath = transactions_stg_path / transaction_data_filename
    # Getting previous (initialization phase) transaction data
    with filepath.open('r') as json_file:
        transaction_data_json = json.load(json_file)

    transaction_data_json['data']['transaction_phase'].append(new_transaction_phase_data_json)

    metadata_updates = get_transaction_data_header_updates(request_t_apdu_jval, response_t_apdu_jval, obe_auth)

    metadata_handler = TransactionMetadataHandler()
    metadata_handler.update_transaction_metadata(filepath.name, metadata_updates)

    # Rewriting transaction data file with new exchange data added
    with filepath.open('w') as json_file:
        json.dump(transaction_data_json, json_file, indent=2)

    return transaction_data_json
