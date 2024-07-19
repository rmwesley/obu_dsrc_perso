import os
import json
from Crypto.Cipher import DES3
from Crypto.Cipher import DES

import logging

key_derivation_logger = logging.getLogger(__name__)

mk_path = os.environ['MK_PATH']
with open(mk_path) as json_file:
    master_keys = json.load(json_file)

# CODE FOR DERIVED ACCESS KEY (Uses MasterKey with ref 120)
def compute_access_key(contract_provider, ac_cr_key_ref):
    # Get the Master Access Key (MAcK)
    try :
        master_access_key = bytes.fromhex(master_keys[contract_provider][8])
    except KeyError as e:
        key_derivation_logger.error(e)
        key_derivation_logger.error(f"We do not possess the masterkeys for Contract Provider {contract_provider}")
        key_derivation_logger.info(f"Please note: TIS instances have security level 0. They are thus not really protected and can be read freely.")
    key_derivation_logger.debug(f"Master Access Key in hex: {master_access_key.hex().upper()}")
    # Prepare the 3DES cipher with the MAcK
    cipher = DES3.new(master_access_key, DES3.MODE_ECB)
    
    # We concatenate the AC_CR-KeyRef 4 times to get 8 bytes
    ciphertext = ac_cr_key_ref.to_bytes(2, 'big') * 4
    key_derivation_logger.debug(f"Ciphertext: {ciphertext.hex().upper()}")

    # Compute the Access Key
    access_key = cipher.encrypt(ciphertext)
    key_derivation_logger.info(f"Access Key in hex: {access_key.hex().upper()}")
    return access_key

def compute_access_credentials(contract_provider, rnd_obe, ac_cr_key_ref):
    # Compute the Access Key
    access_key = compute_access_key(contract_provider, ac_cr_key_ref)
    return compute_access_credentials_with_access_key(contract_provider, rnd_obe, access_key)

def compute_access_credentials_with_access_key(contract_provider, rnd_obe, access_key):
    # Prepare the 3DES cipher with the MAcK
    cipher = DES.new(access_key, DES.MODE_ECB)
    # The padding is automatically added to the right of RndOBE for 3DES
    # We add 4 bytes of padding to the right of RndOBE
    output = cipher.encrypt(rnd_obe + bytearray(4))

    # We now truncate this output to the 4 left-most bytes
    ac_cr = int.from_bytes(output[:4])
    key_derivation_logger.info(f"Access Credentials in hex: {ac_cr:08X}")
    return ac_cr


# CODE FOR DERIVED AUTHENTICATION KEYS (Uses MasterKeys with ref 111 through 118)
def compact_pan_type1(pan_str: str):
    PAN_8 = pan_str[:16]

    most_sbytes = int(PAN_8[:8], 16)
    least_sbytes = int(PAN_8[8:], 16)
    int_compact_pan = most_sbytes ^ least_sbytes

    # Length is 4 bytes, byte ordering is 'big'
    bytes_compact_pan = int_compact_pan.to_bytes(length=4, byteorder="big")
    return bytes_compact_pan


def compute_ciphertext(pan_id, contract_provider):
    # Prepare the compact PAN
    bytes_compact_pan = compact_pan_type1(pan_id)
    # print(bytes_compact_pan.hex())

    # Concatenating a "00" tail and assembling the full ciphertext
    ciphertext_extension = contract_provider + "00"

    bytes_ciphertext_extension = bytes.fromhex(ciphertext_extension)
    ciphertext = bytes_compact_pan + bytes_ciphertext_extension
    # logger.debug(ciphertext.hex())
    # print(ciphertext.hex())
    return ciphertext


def compute_auth_key_with_mauk_value(pan_id: str, contract_provider: str, master_key: bytes):
    # Prepare/configure the cipher with the master key
    cipher = DES3.new(master_key, DES3.MODE_ECB)

    # Prepare the compact PAN
    bytes_compact_pan = compact_pan_type1(pan_id)
    # print(bytes_compact_pan.hex())

    # Concatenating a "00" tail and assembling the full ciphertext
    ciphertext_extension = contract_provider + "00"

    bytes_ciphertext_extension = bytes.fromhex(ciphertext_extension)
    ciphertext = bytes_compact_pan + bytes_ciphertext_extension
    # logger.debug(ciphertext.hex())
    # print(ciphertext.hex())

    auth_key = cipher.encrypt(ciphertext)

    return auth_key.hex().upper()

def compute_auth_key_with_mauk_ref(pan_id: str, contract_provider: str, key_ref: int):
    if key_ref not in range(111, 119):
        raise ValueError("Invalid master authentication key (MAuK) reference!")
    mauk_hex = master_keys[contract_provider][key_ref - 111]
    mauk = bytes.fromhex(mauk_hex)
    return compute_auth_key_with_mauk_value(pan_id, contract_provider, mauk)


def decipher_auth_key_with_mauk_value(auth_key: str, mauk: str):
    bytes_master_key = bytes.fromhex(mauk)
    # Prepare/configure the cipher with the master key
    cipher = DES3.new(bytes_master_key, DES3.MODE_ECB)

    # Decipher
    deciphered_ciphertext = cipher.decrypt(bytes.fromhex(auth_key))

    return deciphered_ciphertext.hex().upper()


def decipher_auth_key_with_mauk_ref(auth_key: str, contract_provider: str, key_number: int):
    mauk = master_keys[contract_provider][key_number - 1]
    return decipher_auth_key_with_mauk_value(auth_key, mauk)