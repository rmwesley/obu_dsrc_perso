import json

import requests
import logging

kapsch_sam_rest_api_logger = logging.getLogger(__name__)
with open('settings/kapsch_sam/kapsch_sam_http_api_conf.json') as json_file:
    kapsch_sam_http_api_conf = json.load(json_file)
    kapsch_sam_origin = kapsch_sam_http_api_conf['Origin']

with open('../security_info/tsp_obu_setup/kapsch_sam_uset_mks_indexes_by_mkset_name_v1.0.0.json', 'r') as json_file:
    kapsch_sam_uset_mks_indexes_by_mkset_name = json.load(json_file)

def compute_uset_derived_key_with_sam_key_index(ac_cr_key_ref:int, uset_key_index:int) -> bytes:
    response = requests.get(url=f'http://{kapsch_sam_origin}/securityservice//keys/index/{uset_key_index}/deriveusetkey/{ac_cr_key_ref:08X}')

    uset_derived_key = bytes.fromhex(response.text)
    kapsch_sam_rest_api_logger.info(f"Derived USET key: 0x{uset_derived_key.hex().upper()}")
    return uset_derived_key

def compute_uset_derived_key(uset_mkset_name:str, ac_cr_key_ref:int) -> bytes:
    uset_key_index = kapsch_sam_uset_mks_indexes_by_mkset_name[uset_mkset_name]

    return compute_uset_derived_key_with_sam_key_index(ac_cr_key_ref, uset_key_index)

# def compute_access_credentials_with_sam_uset_key_index(rnd_obe:int, uset_key_index) -> bytes:
#     requests.get(url=f'http://{kapsch_sam_origin}/securityservice//keys/index/{uset_key_index}/usetcredentials/{ac_cr_key_ref:08X}?rndObe={rnd_obe:08X}')