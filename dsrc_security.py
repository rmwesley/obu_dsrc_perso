import os
import json
from Crypto.Cipher import DES3
from Crypto.Cipher import DES

import logging

key_derivation_logger = logging.getLogger(__name__)

from ASN.compiled_DSRC_instances import EFCv10_1 as EFC

# Loading the Master Keys from a JSON into a Python dict
# This dict maps an EFC-CM in hex format to a MasterKeySet also in hex format
try:
    os.environ['MK_PATH']
except:
    os.environ['MK_PATH'] = r"..\master_keys.json"

mk_path = os.environ['MK_PATH']
master_keys = {}
with open(mk_path) as json_file:
    master_keys_config = json.load(json_file)

    device_type_to_keyset_mapping = master_keys_config["device_type_to_efc_cm_keyset_name_pairs_mapping"]
    for efc_cm_to_keyset_name_mapping in device_type_to_keyset_mapping.values():
        for efc_cm, keyset_name in efc_cm_to_keyset_name_mapping.items():
            master_keys[efc_cm] = master_keys_config['keysets'][keyset_name]

def compute_master_key_kcv(master_key: bytes) -> dict[int, str]:
    return DES3.new(master_key, DES3.MODE_ECB).encrypt(bytearray(8))[:3]

def compute_kcvs_for_efc_cm_keyset(efc_cm: str):
    kcv_dict = {}
    for key_ref, master_key in master_keys[efc_cm].items():
        kcv_dict[key_ref] = compute_master_key_kcv(bytes.fromhex(master_key)).hex().upper()
    return kcv_dict

def prepare_3DES_cipher(efc_cm:str, key_ref:str):
    # In case key_ref is passed as an int instead of string...
    key_ref = str(key_ref)
    efc_cm = efc_cm.upper()
    key_derivation_logger.debug(f"Getting the Master Key with ref {key_ref} for EFC-CM {efc_cm}")
    try :
        master_access_key = bytes.fromhex(master_keys[efc_cm][key_ref])
    except KeyError as e:
        key_derivation_logger.error(e)
        key_derivation_logger.error(f"We do not possess the masterkeys for EFC-CM {efc_cm}")
        key_derivation_logger.info(f"Please note: TIS instances have security level 0. They are thus not really protected and can be read freely.")
        raise(e)
    key_derivation_logger.debug("Preparing the 3DES cipher with the provided Master Key")
    cipher = DES3.new(master_access_key, DES3.MODE_ECB)
    return cipher

# CODE FOR DERIVED ACCESS KEY (Uses MasterKey with ref 120)
def compute_access_key(efc_cm:str, ac_cr_key_ref:int):
    key_derivation_logger.debug("Preparing the Master Access Key (MAcK) 3DES cipher")

    cipher = prepare_3DES_cipher(efc_cm, '120')
    
    # We concatenate the AC_CR-KeyReference 4 times to get 8 bytes
    ciphertext = ac_cr_key_ref.to_bytes(2, 'big') * 4
    key_derivation_logger.debug(f"Ciphertext: {ciphertext.hex().upper()}")

    # Compute the Access Key
    access_key = cipher.encrypt(ciphertext)
    key_derivation_logger.debug(f"Access Key in hex: {access_key.hex().upper()}")
    return access_key

def decrypt_access_key(efc_cm, access_key:bytes):
    key_derivation_logger.debug("Preparing the Master Access Key (MAcK) 3DES cipher")
    cipher = prepare_3DES_cipher(efc_cm, '120')

    decrypted_access_key = cipher.decrypt(access_key)
    key_derivation_logger.info(f"Ciphertext (decrypted access key) in hex: {decrypted_access_key.hex().upper()}")
    return decrypted_access_key

def compute_access_credentials(contract_provider, rnd_obe:int, ac_cr_key_ref:int):
    # Compute the Access Key
    access_key = compute_access_key(contract_provider, ac_cr_key_ref)
    # Compute the Access Credentials and return it
    return compute_access_credentials_with_access_key(rnd_obe, access_key)

def compute_access_credentials_from_t_apdu_with_vst_json(t_apdu_with_vst_json):
    parameter_hex = t_apdu_with_vst_json['initialisation-response']['applications']['parameter']['octetstring']


def compute_access_credentials_with_access_key(rnd_obe:int, access_key):
    # Prepare the DES cipher with the MAcK
    cipher = DES.new(access_key, DES.MODE_ECB)
    # The padding is automatically added to the right of RndOBE for 3DES
    # We add 4 bytes of padding to the right of RndOBE
    output = cipher.encrypt(rnd_obe.to_bytes(4) + bytearray(4))

    # We now truncate this output to the 4 left-most bytes
    ac_cr = int.from_bytes(output[:4])
    key_derivation_logger.debug(f"Access Credentials in hex: {ac_cr:08X}")
    return ac_cr

def compute_authenticator_with_auk_ref(pan_id, efc_cm, attribute_list_bytes, rnd_rse, auk_ref=115) -> bytes:
    authenticator_key = compute_auth_key_with_mauk_ref(pan_id, efc_cm, auk_ref)

    # Prepare the DES cipher with the MAuK
    cipher = DES.new(authenticator_key, DES.MODE_ECB)
    des_output = b''
    right_padding_size = (8 - (len(attribute_list_bytes) + 5)%8)%8
    des_input_bytes = attribute_list_bytes + b'\x04' + rnd_rse.to_bytes(4) + bytearray(right_padding_size)
    
    key_derivation_logger.debug(f"DES input: {des_input_bytes.hex().upper()}")
    for index in range(0, len(des_input_bytes)//8):
        # XOR the 8 output bytes of the last iteration with the next 8 input bytes
        block_of_8_bytes = int.from_bytes(des_input_bytes[index*8 : index*8 + 8])

        key_derivation_logger.debug(f"Index: {index}, Current 8-bytes DES block: {block_of_8_bytes:16X}")
        des_input = int.from_bytes(des_output, 'big') ^ block_of_8_bytes
        des_output = cipher.encrypt(des_input.to_bytes(8))

    authenticator = des_output[0:4]
    return authenticator

def decrypt_auth_key(efc_cm, auth_key:bytes, auk_ref=115):
    key_derivation_logger.debug("Preparing the Master Authentication Key (MAuK) 3DES cipher")
    cipher = prepare_3DES_cipher(efc_cm, auk_ref)

    decrypted_auth_key = cipher.decrypt(auth_key)
    key_derivation_logger.info(f"Ciphertext (decrypted authentication key) in hex: {decrypted_auth_key.hex().upper()}")
    return decrypted_auth_key

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
    key_derivation_logger.debug(f'Compact PAN in hex: {bytes_compact_pan.hex().upper()}')
    if len(bytes_compact_pan) != 4:
        key_derivation_logger.error("Compact PAN should be encoded in 4 bytes!")

    # Concatenating a "00" tail and assembling the full ciphertext
    ciphertext_extension = contract_provider + "00"
    contract_provider_size = len(contract_provider)
    if contract_provider_size != 6:
        key_derivation_logger.error(f"Contract Provider should contain 6 hex characters (3 bytes), not {contract_provider_size} chars!")

    bytes_ciphertext_extension = bytes.fromhex(ciphertext_extension)
    ciphertext = bytes_compact_pan + bytes_ciphertext_extension
    if len(ciphertext) != 8:
        key_derivation_logger.error("Ciphertext should be 8 bytes!!")
        key_derivation_logger.error("Please ensure that the Compact PAN is encoded in 4 bytes and that the Contract Provider is 3 bytes!")
    
    key_derivation_logger.debug(f'Ciphertext in hex: {ciphertext.hex().upper()}')
    return ciphertext

def compute_auth_key_with_mauk_value_and_ciphertext(ciphertext, master_key: bytes):
    # Prepare/configure the cipher with the master key
    try:
        cipher = DES3.new(master_key, DES3.MODE_ECB)
    except:
        return bytes(0)
    
    auth_key = cipher.encrypt(ciphertext)

    key_derivation_logger.debug(f'Computed Auth key: {auth_key.hex().upper()}')
    return auth_key

def compute_auth_key_with_mauk_ref(pan_id: str, efc_cm: str, key_ref: int):
    key_derivation_logger.debug(f'Computing Authentication Key with KeyRef {key_ref} for PAN {pan_id}...')
    key_derivation_logger.debug(f'Getting the Contract Provider. It is encodeed in the first 3 bytes of the EFC-CM...')
    contract_provider = efc_cm[0:6]
    ciphertext = compute_ciphertext(pan_id, contract_provider)
    
    if key_ref not in range(111, 119):
        raise ValueError("Invalid master authentication key (MAuK) reference!")
    mauk_hex = master_keys[efc_cm][str(key_ref)]
    mauk = bytes.fromhex(mauk_hex)
    return compute_auth_key_with_mauk_value_and_ciphertext(ciphertext, mauk)

def compute_all_auth_keys(pan_id: str, efc_cm: str):
    key_derivation_logger.debug(f'Computing all 8 Authentication Keys for PAN {pan_id}')
    key_derivation_logger.debug(f'Getting the Contract Provider. It is encodeed in the first 3 bytes of the EFC-CM...')
    contract_provider = efc_cm[0:6]
    ciphertext = compute_ciphertext(pan_id, contract_provider)
    
    auth_keys = {}
    for key_ref in range(111, 119):
        mauk_hex = master_keys[efc_cm][str(key_ref)]
        mauk = bytes.fromhex(mauk_hex)
        auth_keys[key_ref] = compute_auth_key_with_mauk_value_and_ciphertext(ciphertext, mauk)
    return auth_keys

def compute_all_auth_keys_and_return_hex_dict(pan_id:str, efc_cm:str):
    auth_keys_dict = compute_all_auth_keys(pan_id, efc_cm)
    return {key_ref: computed_auk.hex().upper() for (key_ref, computed_auk) in auth_keys_dict.items()}

def compute_all_derived_keys_and_return_hex_dict(pan_id:str, efc_cm:str, ac_cr_key_ref:int):
    derived_keys_dict = compute_all_auth_keys(pan_id, efc_cm)
    derived_keys_dict[120] = compute_access_key(efc_cm, ac_cr_key_ref)
    return {key_ref: computed_auk.hex().upper() for (key_ref, computed_auk) in derived_keys_dict.items()}

def compute_all_derived_keys_for_device_type_and_return_hex_dict(pan_id:str, device_type:str, ac_cr_key_ref:int):
    efc_cm_to_derived_keys = {}
    for efc_cm, keyset_name in device_type_to_keyset_mapping[device_type].items():
        derived_keys_dict = compute_all_auth_keys(pan_id, efc_cm)
        derived_keys_dict[120] = compute_access_key(efc_cm, ac_cr_key_ref)
        efc_cm_to_derived_keys[efc_cm] = {key_ref: computed_auk.hex().upper() for (key_ref, computed_auk) in derived_keys_dict.items()}
    return efc_cm_to_derived_keys


def compute_all_derived_keys_for_available_keysets_and_return_hex_dict(pan_id:str, ac_cr_key_ref:int):
    efc_cm_to_derived_keys = {}
    for efc_cm in master_keys:
        derived_keys_dict = compute_all_auth_keys(pan_id, efc_cm)
        derived_keys_dict[120] = compute_access_key(efc_cm, ac_cr_key_ref)
        efc_cm_to_derived_keys[efc_cm] = {key_ref: computed_auk.hex().upper() for (key_ref, computed_auk) in derived_keys_dict.items()}
    return efc_cm_to_derived_keys

def decipher_auth_key_with_mauk_value(auth_key: str, mauk: str) -> bytes:
    bytes_master_key = bytes.fromhex(mauk)
    # Prepare/configure the cipher with the master key
    cipher = DES3.new(bytes_master_key, DES3.MODE_ECB)

    # Decipher
    deciphered_ciphertext = cipher.decrypt(bytes.fromhex(auth_key))

    return deciphered_ciphertext


def decipher_auth_key_with_mauk_ref(auth_key: str, efc_cm: str, key_ref: int) -> bytes:
    mauk = master_keys[efc_cm][str(key_ref)]
    return decipher_auth_key_with_mauk_value(auth_key, mauk)