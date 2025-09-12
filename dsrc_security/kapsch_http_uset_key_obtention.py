import json
import datetime
import requests

import logging
kapsch_http_uset_req_logger = logging.getLogger(__name__)

startup_date = datetime.datetime.now()
logs_date_prefix = startup_date.strftime('%y%m%d')

# SETTING UP LOGGER FILE HANDLER
file_handler = logging.FileHandler(f'logs/beacon_logs/{logs_date_prefix}_kapsch_http_logs.log')
file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)
kapsch_http_uset_req_logger.addHandler(file_handler)

base_url = ''
with open('settings/perso/kapsch_uset_app_config.json') as json_file:
    kapsch_uset_app_config = json.load(json_file)
    base_url = kapsch_uset_app_config['baseUrl']

class KapschHttpWsError(Exception):
    pass
http_ws_timeout = 0.2
def send_get_request_to_web_service(route:str):
    global base_url

    url = f'{base_url}/tsp_dsrc_sec/{route}'
    try:
        response = requests.get(url, timeout=http_ws_timeout)
    except requests.exceptions.ConnectTimeout as e:
        raise KapschHttpWsError(f'HTTP GET {url} failed. (Connection timeout={http_ws_timeout}s)')
        # raise KapschHttpWsError(str(e))

    kapsch_http_uset_req_logger.debug(f'HTTP Response: {response}')
    kapsch_http_uset_req_logger.debug(response.text)
    return response

def compute_uset_derived_key_via_mk_name(uset_mk_name:str, ac_cr_key_ref:int) -> bytes:
    ac_cr_key_ref_hex = f'{ac_cr_key_ref:04X}'
    route=f'uset_masterkeys/{uset_mk_name}/derived_keys/{ac_cr_key_ref_hex}'
    response = send_get_request_to_web_service(route)
    return bytes.fromhex(response.text)

def get_decrypted_kapsch_uset_key_via_mk_name(uset_mk_name:str, uset_derived_key_hex:str):
    route = f'uset_masterkeys/{uset_mk_name}/decrypt_uset_key/{uset_derived_key_hex}'
    response = send_get_request_to_web_service(route)
    return bytes.fromhex(response.text)

def compute_kapsch_uset_access_credentials_via_mk_name(uset_mk_name:str, ac_cr_key_ref:int, rnd_obe:int) -> bytes:
    ac_cr_key_ref_hex = f'{ac_cr_key_ref:04X}'
    rnd_obe_hex = f'{rnd_obe:08X}'
    route = f'uset_masterkeys/{uset_mk_name}/derived_keys/{ac_cr_key_ref_hex}/ac_cr/{rnd_obe_hex}'
    response = send_get_request_to_web_service(route)
    return bytes.fromhex(response.text)

def get_uset_derived_key_for_obu_model(obu_model:str, uset_key_type, ac_cr_key_ref:int) -> bytes:
    ac_cr_key_ref_hex = f'{ac_cr_key_ref:04X}'
    route = f'obu_models/{obu_model}/uset_key_types/{uset_key_type}/derived_keys/{ac_cr_key_ref_hex}'
    response = send_get_request_to_web_service(route)
    return bytes.fromhex(response.text)

def get_decrypted_kapsch_uset_key_for_obu_model(obu_model_name:str, uset_key_type, uset_derived_key_hex:str):
    route = f'obu_models/{obu_model_name}/uset_key_types/{uset_key_type}/decrypt_uset_key/{uset_derived_key_hex}'
    response = send_get_request_to_web_service(route)
    return bytes.fromhex(response.text)

def get_kapsch_uset_access_credentials_for_obu_model(obu_model:str, uset_key_type, ac_cr_key_ref:int, rnd_obe:int) -> bytes:
    ac_cr_key_ref_hex = f'{ac_cr_key_ref:04X}'
    rnd_obe_hex = f'{rnd_obe:08X}'
    route = f'obu_models/{obu_model}/uset_key_types/{uset_key_type}/derived_keys/{ac_cr_key_ref_hex}/ac_cr/{rnd_obe_hex}'
    response = send_get_request_to_web_service(route)
    return bytes.fromhex(response.text)