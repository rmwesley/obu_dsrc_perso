from Crypto.Cipher import DES, DES3

import json
import logging
import typing

import kapsch_uset_derivation
# import kapsch_sam_http_api_sec_ops as kapsch_uset_derivation

perso_secops_logger = logging.getLogger(__name__)

uset_mkset_name_by_obu_model_and_key_type = {}
with open('../security_info/tsp_obu_setup/axxes_kapsch_uset_mkset_by_obu_model_v2.0.0.json', 'r') as json_file:
    uset_mkset_name_by_obu_model_and_key_type = json.load(json_file)

default_uset_key_type = 'Exploit'
TRP_4010_20B_MK_TYPES = typing.Literal['SystemElementAcK', 'Stock', 'Exploit']
def set_default_key_type(uset_key_type:TRP_4010_20B_MK_TYPES):
    global default_uset_key_type
    default_uset_key_type = uset_key_type

def compute_uset_derived_key_for_obu_model(obu_model:str, ac_cr_key_ref:int, uset_key_type=default_uset_key_type) -> bytes:
    if not uset_key_type:
        uset_key_type = default_uset_key_type

    uset_mkset_name = uset_mkset_name_by_obu_model_and_key_type[obu_model]['uset_mk_info'][uset_key_type]

    return kapsch_uset_derivation.compute_uset_derived_key(uset_mkset_name=uset_mkset_name, ac_cr_key_ref=ac_cr_key_ref)

def decrypt_uset_derived_key_for_obu_model(obu_model:str, ciphertext:bytes, uset_key_type=default_uset_key_type) -> bytes:
    if not uset_key_type:
        uset_key_type = default_uset_key_type

    uset_mkset_name = uset_mkset_name_by_obu_model_and_key_type[obu_model]['uset_mk_info'][uset_key_type]

    return kapsch_uset_derivation.decrypt_uset_derived_key(uset_mkset_name=uset_mkset_name, ciphertext=ciphertext)

class ObuModelUnknown(Exception):
    pass

def compute_access_credentials_with_8_bytes_uset_key(rnd_obe:int, uset_derived_key) -> bytes:
    # Prepare the DES cipher with the derivec Access Key/USET Key
    cipher = DES.new(uset_derived_key, DES.MODE_ECB)
    # The padding is automatically added to the right of RndOBE for DES
    # We add 4 bytes of padding to the right of RndOBE
    output = cipher.encrypt(rnd_obe.to_bytes(4) + bytearray(4))

    # We now truncate this output to the 4 left-most bytes
    ac_cr = output[:4]
    perso_secops_logger.debug(f"Access Credentials in hex: {ac_cr.hex().upper()}")
    return ac_cr

def compute_access_credentials_with_16_bytes_uset_key(rnd_obe:int, uset_derived_key) -> bytes:
    # print(uset_derived_key)
    cipher = DES3.new(uset_derived_key, DES3.MODE_ECB)
    output = cipher.encrypt(rnd_obe.to_bytes(4) + bytearray(4))

    ac_cr = output[:4]
    perso_secops_logger.debug(f"Access Credentials in hex: {ac_cr.hex().upper()}")
    return ac_cr
compute_access_credentials_with_32_bytes_uset_key = compute_access_credentials_with_16_bytes_uset_key

def compute_access_credentials_with_uset_key(rnd_obe:int, uset_derived_key) -> bytes:
    if len(uset_derived_key) == 8:
        uset_ac_cr = compute_access_credentials_with_8_bytes_uset_key(rnd_obe, uset_derived_key)
    if len(uset_derived_key) == 16:
        uset_ac_cr = compute_access_credentials_with_16_bytes_uset_key(rnd_obe, uset_derived_key)
    if len(uset_derived_key) == 32:
        uset_ac_cr = compute_access_credentials_with_32_bytes_uset_key(rnd_obe, uset_derived_key)
    return uset_ac_cr

def compute_kapsch_uset_access_credentials_for_obu_model(obu_model:str, ac_cr_key_ref:int, rnd_obe:int, uset_key_type=default_uset_key_type) -> bytes:
    if uset_key_type is None:
        uset_key_type = default_uset_key_type

    uset_derived_key = compute_uset_derived_key_for_obu_model(obu_model, ac_cr_key_ref, uset_key_type)
    return compute_access_credentials_with_uset_key(rnd_obe, uset_derived_key)

class InvalidObuModel(Exception):
    pass
def check_obu_model_and_compute_kapsch_uset_access_credentials_for_obu_model(expected_obu_eq_ref:str, obu_model:str, ac_cr_key_ref:int, rnd_obe:int, uset_key_type=default_uset_key_type) -> bytes:
    if uset_key_type is None:
        uset_key_type = default_uset_key_type
    if expected_obu_eq_ref not in uset_mkset_name_by_obu_model_and_key_type[obu_model]['supported_obu_eq_refs']:
        raise InvalidObuModel(f'OBU with Manufacturer Id/Equipment Class 0x{expected_obu_eq_ref} is not of model {obu_model}')

    return compute_kapsch_uset_access_credentials_for_obu_model(obu_model, ac_cr_key_ref, rnd_obe, uset_key_type)

# USET key update dict preparation function
def get_eid_and_new_uset_attribute_dict(eid:int, obu_model:str, ac_cr_key_ref:int, new_uset_key_type=default_uset_key_type) -> tuple[int, dict]:
    uset_key_info = uset_mkset_name_by_obu_model_and_key_type[obu_model]['dsrc_mem_key_locations'][eid]['uset_key']

    uset_key_eid = eid
    # USET key EID is normally the same EID, otherwise, the key is stored in another element.
    # This is a workaround used for TIS-VL EFC elements, since they use attribute IDs 111 through 118 for historization (D-HIS)!
    if 'external_eid' in uset_key_info:
        uset_key_eid = uset_key_info['external_eid']

    uset_key_attr_id = uset_key_info['storage_attr_id']
    uset_key_bytes = compute_uset_derived_key_for_obu_model(obu_model, ac_cr_key_ref, new_uset_key_type)

    # 0x02 = EfcContainer CHOICE tag for OCTET STRING
    uset_key_octet_string_uper_hex = f'02{len(uset_key_bytes):02X}{uset_key_bytes.hex().upper()}'
    new_uset_attr_dict = {
        uset_key_attr_id: uset_key_octet_string_uper_hex
    }
    return uset_key_eid, new_uset_attr_dict
