from Crypto.Cipher import DES, DES3

import json
import logging
import typing

perso_logger = logging.getLogger(__name__)

with open('../security_info/tsp_obu_setup/axxes_kapsch_uset_mksets_v1.0.0.json', 'r') as json_file:
    uset_mksets = json.load(json_file)

uset_mks_by_obu_model_and_key_type = {}
with open('../security_info/tsp_obu_setup/axxes_kapsch_uset_mkset_by_obu_model_v1.0.0.json', 'r') as json_file:
    perso_security_conf = json.load(json_file)
    for obu_model, obu_model_sec_info in perso_security_conf.items():
        for uset_key_type, keyset_name in obu_model_sec_info['master_key_info'].items():
            uset_mks_by_obu_model_and_key_type[obu_model][uset_key_type] = bytes.fromhex(uset_mksets[keyset_name]['mk_hex_value'])

default_uset_key_type = 'Exploit'
TRP_4010_20B_MK_TYPES = typing.Literal['SystemElementAcK', 'Stock', 'Exploit']
def set_default_key_type(uset_key_type:TRP_4010_20B_MK_TYPES):
    global default_uset_key_type
    default_uset_key_type = uset_key_type

class ObuModelUnknown(Exception):
    pass

# Not supported!!
def compute_uset_derived_key_8_bytes_mk(uset_master_key:bytes, ac_cr_key_ref:int) -> bytes:
    ac_cr_key_ref_bytes = ac_cr_key_ref.to_bytes(length=2)
    plaintext = ac_cr_key_ref_bytes * 4

    cipher = DES.new(key=uset_master_key[0:8], mode=DES3.MODE_ECB)
    ciphertext = cipher.encrypt(plaintext)

    return ciphertext

def compute_uset_derived_key_16_bytes_mk(uset_master_key:bytes, ac_cr_key_ref:int) -> bytes:
    ac_cr_key_ref_bytes = ac_cr_key_ref.to_bytes(length=2)
    plaintext = ac_cr_key_ref_bytes * 4

    cipher = DES3.new(key=uset_master_key[0:16], mode=DES3.MODE_ECB)
    ciphertext = cipher.encrypt(plaintext)

    return ciphertext

def compute_uset_derived_key_32_bytes_mk(uset_master_key:bytes, ac_cr_key_ref:int) -> bytes:
    ac_cr_key_ref_bytes = ac_cr_key_ref.to_bytes(length=2)
    plaintext = ac_cr_key_ref_bytes * 4

    cipher1 = DES3.new(key=uset_master_key[0:16], mode=DES3.MODE_ECB)
    uset_key_part1 = cipher1.encrypt(plaintext)
    cipher2 = DES3.new(key=uset_master_key[16:32], mode=DES3.MODE_ECB)
    uset_key_part2 = cipher2.encrypt(plaintext)

    return uset_key_part1 + uset_key_part2

def compute_uset_derived_key(uset_master_key:bytes, ac_cr_key_ref:int) -> bytes:
    if len(uset_master_key) == 8:
        uset_derived_key = compute_uset_derived_key_8_bytes_mk(uset_master_key, ac_cr_key_ref)
    if len(uset_master_key) == 16:
        uset_derived_key = compute_uset_derived_key_16_bytes_mk(uset_master_key, ac_cr_key_ref)
    if len(uset_master_key) == 32:
        uset_derived_key = compute_uset_derived_key_32_bytes_mk(uset_master_key, ac_cr_key_ref)

    perso_logger.info(f"Derived USET key: 0x{uset_derived_key.hex().upper()}")
    return uset_derived_key

def compute_uset_derived_key_for_obu_model(obu_model:str, ac_cr_key_ref:int, uset_key_type=default_uset_key_type) -> bytes:
    if not uset_key_type:
        uset_key_type = default_uset_key_type

    uset_mk_bytes = uset_mks_by_obu_model_and_key_type[obu_model][uset_key_type]

    return compute_uset_derived_key(uset_master_key=uset_mk_bytes, ac_cr_key_ref=ac_cr_key_ref)

def decrypt_uset_derived_key_8_bytes_mk(uset_master_key:bytes, ciphertext:bytes) -> bytes:
    cipher = DES.new(key=uset_master_key[0:8], mode=DES3.MODE_ECB)
    plaintext = cipher.decrypt(ciphertext[0:4])

    return plaintext

def decrypt_uset_derived_key_16_bytes_mk(uset_master_key:bytes, ciphertext:bytes) -> bytes:
    cipher = DES3.new(key=uset_master_key[0:16], mode=DES3.MODE_ECB)
    plaintext = cipher.decrypt(ciphertext[0:8])

    return plaintext

def decrypt_uset_derived_key_32_bytes_mk(uset_master_key:bytes, ciphertext:bytes) -> bytes:
    cipher1 = DES3.new(key=uset_master_key[0:16], mode=DES3.MODE_ECB)
    plaintext_part1 = cipher1.decrypt(ciphertext[0:8])
    cipher2 = DES3.new(key=uset_master_key[16:32], mode=DES3.MODE_ECB)
    plaintext_part2 = cipher2.decrypt(ciphertext[8:16])

    return plaintext_part1 + plaintext_part2

def decrypt_uset_derived_key(uset_master_key:bytes, ciphertext:bytes) -> bytes:
    if len(uset_master_key) == 8:
        return decrypt_uset_derived_key_8_bytes_mk(uset_master_key, ciphertext)
    if len(uset_master_key) == 16:
        return decrypt_uset_derived_key_16_bytes_mk(uset_master_key, ciphertext)
    if len(uset_master_key) == 32:
        return decrypt_uset_derived_key_32_bytes_mk(uset_master_key, ciphertext)

def decrypt_uset_derived_key_for_obu_model(obu_model:str, ciphertext:bytes, uset_key_type=default_uset_key_type) -> bytes:
    if not uset_key_type:
        uset_key_type = default_uset_key_type

    uset_mk_bytes = bytes.fromhex(uset_mks_by_obu_model_and_key_type[obu_model][uset_key_type])

    return decrypt_uset_derived_key(uset_master_key=uset_mk_bytes, ciphertext=ciphertext)

def compute_access_credentials_with_8_bytes_uset_key(rnd_obe:int, uset_derived_key) -> bytes:
    # Prepare the DES cipher with the derivec Access Key/USET Key
    cipher = DES.new(uset_derived_key, DES.MODE_ECB)
    # The padding is automatically added to the right of RndOBE for DES
    # We add 4 bytes of padding to the right of RndOBE
    output = cipher.encrypt(rnd_obe.to_bytes(4) + bytearray(4))

    # We now truncate this output to the 4 left-most bytes
    ac_cr = output[:4]
    perso_logger.debug(f"Access Credentials in hex: {ac_cr.hex().upper()}")
    return ac_cr

def compute_access_credentials_with_16_bytes_uset_key(rnd_obe:int, uset_derived_key) -> bytes:
    # print(uset_derived_key)
    cipher = DES3.new(uset_derived_key, DES3.MODE_ECB)
    output = cipher.encrypt(rnd_obe.to_bytes(4) + bytearray(4))

    ac_cr = output[:4]
    perso_logger.debug(f"Access Credentials in hex: {ac_cr.hex().upper()}")
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
    if expected_obu_eq_ref not in perso_security_conf[obu_model]:
        raise InvalidObuModel(f'OBU with Manufacturer Id/Equipment Class 0x{expected_obu_eq_ref} is not of model {obu_model}')

    return compute_kapsch_uset_access_credentials_for_obu_model(obu_model, ac_cr_key_ref, rnd_obe, uset_key_type)
