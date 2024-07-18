import os
import json
from Crypto.Cipher import DES3
from Crypto.Cipher import DES

import logging

key_derivation_logger = logging.getLogger(__name__)

mk_path = os.environ['MK_PATH']
with open(mk_path) as json_file:
    master_keys = json.load(json_file)

def compute_access_key(issuer_id, ac_cr_key_ref):
    # issuer_id = EFC-CM or ContractProvider
    # Get the Master Access Key (MAcK)t
    try :
        master_access_key = bytes.fromhex(master_keys[issuer_id][8])
    except KeyError as e:
        key_derivation_logger.error(e)
        key_derivation_logger.error(f"We do not possess the masterkeys for issuer {issuer_id}")
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

def compute_access_credentials(issuer_id, rnd_obe, ac_cr_key_ref):
    # Compute the Access Key
    access_key = compute_access_key(issuer_id, ac_cr_key_ref)
    return compute_access_credentials_with_access_key(issuer_id, rnd_obe, access_key)

def compute_access_credentials_with_access_key(issuer_id, rnd_obe, access_key):
    # Prepare the 3DES cipher with the MAcK
    cipher = DES.new(access_key, DES.MODE_ECB)
    # The padding is automatically added to the right of RndOBE for 3DES
    # We add 4 bytes of padding to the right of RndOBE
    output = cipher.encrypt(rnd_obe + bytearray(4))

    # We now truncate this output to the 4 left-most bytes
    ac_cr = int.from_bytes(output[:4])
    key_derivation_logger.info(f"Access Credentials in hex: {ac_cr:08X}")
    return ac_cr