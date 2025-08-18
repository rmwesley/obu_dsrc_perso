from Crypto.Cipher import DES3

import json
import logging
import typing

perso_logger = logging.getLogger(__name__)

perso_env = 'TEST'
with open('../security_info/tsp_obu_setup/perso_config_and_obu_models_v1.0.1.json', 'r') as json_file:
    perso_config = json.load(json_file)

with open('../security_info/tsp_obu_setup/axxes_kapsch_tis_uset_master_keys.json', 'r') as json_file:
    axxes_kapsch_uset_master_keys = json.load(json_file)[perso_env]

TRP_4010_20B_MK_TYPES = typing.Literal['Factory', 'Stock', 'Exploit']
def set_default_key_type(uset_key_type:TRP_4010_20B_MK_TYPES):
    global default_uset_key_type
    default_uset_key_type = uset_key_type

# def notify_obu_with_no_contract(obu_eq_ref:str):
#     efc_cm = obu_eq_ref[0:12]
#     if efc_cm in ['00000000000000', '010101010101', '020202020202', '030303030303']:
#         raise NoValidObeEfcmFoundInVst(f'OBU has invalid EFC-CM: (0x{efc_cm_hex})!')

# def get_mks_from_keyset_name(keyset_name):
#     return master_keys[keyset_name]

class ObuModelUnknown(Exception):
    pass

def get_uset_derived_key(uset_master_key:bytes, ac_cr_key_ref:int) -> bytes:
    ac_cr_key_ref_bytes = ac_cr_key_ref.to_bytes(length=2)
    plaintext = ac_cr_key_ref_bytes * 4

    cipher1 = DES3.new(key=uset_master_key[0:16], mode=DES3.MODE_ECB)
    uset_key_part1 = cipher1.encrypt(plaintext)
    cipher2 = DES3.new(key=uset_master_key[16:32], mode=DES3.MODE_ECB)
    uset_key_part2 = cipher2.encrypt(plaintext)

    return uset_key_part1 + uset_key_part2

def get_uset_derived_key_for_obu_model(obu_model:str, ac_cr_key_ref:int, uset_key_type=default_uset_key_type) -> bytes:
    if not uset_key_type:
        uset_key_type = default_uset_key_type

    uset_mk_hex = axxes_kapsch_uset_master_keys[obu_model][uset_key_type]
    uset_mk_bytes = bytes.fromhex(uset_mk_hex)

    return get_uset_derived_key(uset_master_key=uset_mk_bytes, ac_cr_key_ref=ac_cr_key_ref)

def decrypt_uset_derived_key(uset_master_key:bytes, ciphertext:bytes) -> bytes:
    cipher1 = DES3.new(key=uset_master_key[0:16], mode=DES3.MODE_ECB)
    plaintext_part1 = cipher1.decrypt(ciphertext[0:8])
    cipher2 = DES3.new(key=uset_master_key[16:32], mode=DES3.MODE_ECB)
    plaintext_part2 = cipher2.decrypt(ciphertext[8:16])

    return plaintext_part1 + plaintext_part2

def decrypt_uset_derived_key_for_obu_model(obu_model:str, ciphertext:bytes, uset_key_type=default_uset_key_type) -> bytes:
    if not uset_key_type:
        uset_key_type = default_uset_key_type

    uset_mk_hex = axxes_kapsch_uset_master_keys[obu_model][uset_key_type]
    uset_mk_bytes = bytes.fromhex(uset_mk_hex)

    return decrypt_uset_derived_key(uset_master_key=uset_mk_bytes, ciphertext=ciphertext)

set_default_key_type('Stock')