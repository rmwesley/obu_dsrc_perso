from Crypto.Cipher import DES

import logging
from dsrc_security import dsrc_key_derivation

dsrc_auth_logger = logging.getLogger(__name__)

# Remember to set the key derivation settings for the Toll Domain!!
# 2 key derivation algorithms are implemented.
# One follows EN15509, and the other follow the TIS decimal profile.

def compute_access_credentials(efc_cm:str, rnd_obe:int, ac_cr_key_ref:int):
    # Compute the Access Key
    access_key = dsrc_key_derivation.compute_ack_with_efc_cm_only(efc_cm, ac_cr_key_ref)
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
    dsrc_auth_logger.debug(f"Access Credentials in hex: {ac_cr:08X}")
    return ac_cr

def compute_authenticator_with_auk_value(attribute_list_bytes, rnd_rse, auk_value:bytes):
    # Prepare the DES cipher with the MAuK
    cipher = DES.new(auk_value, DES.MODE_ECB)
    des_output = b''
    right_padding_size = (8 - (len(attribute_list_bytes) + 5)%8)%8
    des_input_bytes = attribute_list_bytes + b'\x04' + rnd_rse.to_bytes(4) + bytearray(right_padding_size)
    
    dsrc_auth_logger.debug(f"DES input: {des_input_bytes.hex().upper()}")
    for index in range(0, len(des_input_bytes)//8):
        # XOR the 8 output bytes of the last iteration with the next 8 input bytes
        block_of_8_bytes = int.from_bytes(des_input_bytes[index*8 : index*8 + 8])

        dsrc_auth_logger.debug(f"Index: {index}, Current 8-bytes DES block: {block_of_8_bytes:16X}")
        des_input = int.from_bytes(des_output, 'big') ^ block_of_8_bytes
        des_output = cipher.encrypt(des_input.to_bytes(8))

    attr_authenticator = des_output[0:4]
    return attr_authenticator

def compute_authenticator_with_auk_ref(pan_bytes:bytes, efc_cm, attribute_list_bytes, rnd_rse, auk_ref=115) -> bytes:
    # Obtaining AuK via EFC-CM only info (not ideal!!)
    authenticator_key = dsrc_key_derivation.compute_auk_with_efc_cm_and_auk_ref(pan_bytes, efc_cm, auk_ref)

    attr_authenticator = compute_authenticator_with_auk_value(attribute_list_bytes, rnd_rse, auk_value=authenticator_key)
    dsrc_auth_logger.info(f"[OBE AUTH] Authenticator computed by RSE (UPER hex): {attr_authenticator.hex().upper()}")
    return attr_authenticator

def compute_authenticator_with_device_contract_ref_and_auk_ref(pan_bytes:bytes, device_contract_ref:str, attribute_list_bytes, rnd_rse, auk_ref=115) -> bytes:
    # Obtaining AuK via device_contract_ref
    authenticator_key = dsrc_key_derivation.compute_auk_with_device_contract_ref_and_auk_ref(pan_bytes, device_contract_ref, auk_ref)

    attr_authenticator = compute_authenticator_with_auk_value(attribute_list_bytes, rnd_rse, auk_value=authenticator_key)
    dsrc_auth_logger.info(f"[OBE AUTH] Authenticator computed by RSE (UPER hex): {attr_authenticator.hex().upper()}")
    return attr_authenticator

def compute_authenticator_with_device_info_and_auk_ref(pan_bytes:bytes, efc_cm_hex_str: str, manufacturer_id_hex_str:str, equipment_class_hex_str: str, attribute_list_bytes, rnd_rse, auk_ref=115) -> bytes:
    # Obtaining AuK via device info
    authenticator_key = dsrc_key_derivation.compute_auk_with_device_info_and_auk_ref(pan_bytes, efc_cm_hex_str, manufacturer_id_hex_str, equipment_class_hex_str, auk_ref)

    attr_authenticator = compute_authenticator_with_auk_value(attribute_list_bytes, rnd_rse, auk_value=authenticator_key)
    dsrc_auth_logger.info(f"[OBE AUTH] Authenticator computed by RSE (UPER hex): {attr_authenticator.hex().upper()}")
    return attr_authenticator