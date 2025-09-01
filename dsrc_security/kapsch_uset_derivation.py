from Crypto.Cipher import DES, DES3
import json
import logging

kapsch_uset_logger = logging.getLogger(__name__)

with open('../security_info/tsp_obu_setup/axxes_kapsch_uset_mksets_v1.0.0.json', 'r') as json_file:
    uset_mksets = json.load(json_file)

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

def compute_uset_derived_key_with_mk(uset_master_key:bytes, ac_cr_key_ref:int) -> bytes:
    if len(uset_master_key) == 8:
        uset_derived_key = compute_uset_derived_key_8_bytes_mk(uset_master_key, ac_cr_key_ref)
    if len(uset_master_key) == 16:
        uset_derived_key = compute_uset_derived_key_16_bytes_mk(uset_master_key, ac_cr_key_ref)
    if len(uset_master_key) == 32:
        uset_derived_key = compute_uset_derived_key_32_bytes_mk(uset_master_key, ac_cr_key_ref)

    kapsch_uset_logger.info(f"Derived USET key: 0x{uset_derived_key.hex().upper()}")
    return uset_derived_key

def compute_uset_derived_key(uset_mkset_name:str, ac_cr_key_ref:int) -> bytes:
    uset_master_key = bytes.fromhex(uset_mksets[uset_mkset_name])

    return compute_uset_derived_key_with_mk(uset_master_key, ac_cr_key_ref)

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

def decrypt_uset_derived_key_with_mk(uset_master_key:bytes, ciphertext:bytes) -> bytes:
    if len(uset_master_key) == 8:
        return decrypt_uset_derived_key_8_bytes_mk(uset_master_key, ciphertext)
    if len(uset_master_key) == 16:
        return decrypt_uset_derived_key_16_bytes_mk(uset_master_key, ciphertext)
    if len(uset_master_key) == 32:
        return decrypt_uset_derived_key_32_bytes_mk(uset_master_key, ciphertext)

def decrypt_uset_derived_key(uset_mkset_name:str, ciphertext:bytes) -> bytes:
    uset_master_key = bytes.fromhex(uset_mksets[uset_mkset_name])

    return decrypt_uset_derived_key_with_mk(uset_master_key, ciphertext)