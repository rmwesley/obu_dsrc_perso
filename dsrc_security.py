import os
import json
import iso3166
import custom_its_per_decoders

from Crypto.Cipher import DES3
from Crypto.Cipher import DES

import logging

key_derivation_logger = logging.getLogger(__name__)

from ASN.compiled_DSRC_instances import EFCv10_1 as EFC

# Loading the Master Keys from a JSON into a Python dict
# This dict maps an EFC-CM in hex format to a MasterKeySet also in hex format
try:
    os.environ['EFC_SEC_CONF_PATH']
except:
    os.environ['EFC_SEC_CONF_PATH'] = r"..\efc_security_config_v2.2.3.json"

efc_sec_conf_path = os.environ['EFC_SEC_CONF_PATH']

def assemble_device_contract_ref_hex_str(efc_cm_hex_str: str, manufacturer_id_hex_str:str, equipment_class_hex_str:str):
    if type(manufacturer_id_hex_str) is int:
        manufacturer_id_hex_str = f'{manufacturer_id:04X}'
    if type(equipment_class_hex_str) is int:
        equipment_class_hex_str = f'{equipment_class_hex_str:04X}'
    if type(efc_cm_hex_str) is int:
        efc_cm_hex_str = f'{efc_cm_hex_str:12X}'

    if type(manufacturer_id_hex_str) is bytes:
        manufacturer_id_hex_str = manufacturer_id_hex_str.hex().upper()
    if type(equipment_class_hex_str) is bytes:
        equipment_class_hex_str = equipment_class_hex_str.hex().upper()
    if type(efc_cm_hex_str) is bytes:
        efc_cm_hex_str = efc_cm_hex_str.hex().upper()

    device_contract_hex_ref = f'{efc_cm_hex_str}{manufacturer_id_hex_str}{equipment_class_hex_str}'
    return device_contract_hex_ref

equipment_refs_by_device_names = {}
master_keys_by_toll_domain = {}
with open(efc_sec_conf_path) as json_file:
    efc_security_config = json.load(json_file)
    # Device name to Manufacturer Id + Equipment Class mapping (in hex!!)
    equipment_refs_by_device_names = efc_security_config['equipment_references_by_device_model_name']

    # Setting up EFC-CM + Equipment Class to Master Key mapping, by Toll Domain!
    for toll_domain_name, contracts_by_manufacturer in efc_security_config['device_contracts_by_toll_domain'].items():
        # Assembling masterkeys for a Toll Domain!!
        master_keys_by_toll_domain[toll_domain_name] = {}
        for manufacturer_id_hex, device_details_by_equipment_class in contracts_by_manufacturer.items():
            for equipment_class_hex, device_details in device_details_by_equipment_class.items():
                contract_data = device_details['EFC_contract_data']
                keyset_name = contract_data['keyset_name']
                efc_cm = contract_data['EFC-CM']

                # This dictionary makes it easier to find a keyset!!
                # The dictionary keys are a concatenation of the EFC-CM, Manufacturer Id and Equipment Class!!
                device_contract_ref = assemble_device_contract_ref_hex_str(efc_cm, manufacturer_id_hex, equipment_class_hex)

                master_keys_by_toll_domain[toll_domain_name][device_contract_ref] = efc_security_config['keysets'][keyset_name]

    # toll_domain_security_profiles = efc_security_config['toll_domain_security_profiles']
    del efc_security_config

class TollDomainException(Exception):
    pass

with open('settings/toll_domain_config.json') as json_file:
    toll_domain_config_json = json.load(json_file)
    default_toll_domain_name = toll_domain_config_json['default_toll_domain_name']
    td_conf_by_td_name = toll_domain_config_json['td_conf_by_td_name']

current_toll_domain_name = 'TIS'
current_security_profile = 'TIS_decimal'
master_keys_by_device_contract_ref = {}
def set_toll_domain(toll_domain_name:str):
    global current_toll_domain_name
    global current_security_profile
    global master_keys_by_device_contract_ref

    if toll_domain_name not in master_keys_by_toll_domain:
        raise TollDomainException('NO MASTERKEYS FOUND FOR GIVEN TOLL DOMAIN')
    current_toll_domain_name = toll_domain_name
    current_security_profile = td_conf_by_td_name[current_toll_domain_name]['security_profile']
    master_keys_by_device_contract_ref = master_keys_by_toll_domain[current_toll_domain_name]

set_toll_domain(toll_domain_name=default_toll_domain_name)

def get_master_keys(efc_cm_hex_str: str, manufacturer_id_hex_str:str, equipment_class_hex_str:str):
    """Get master keys through device (OBE) model data and EFC contract data
    All of these should be present in the OBE's VST!!!"""
    global master_keys_by_device_contract_ref
    try:
        device_contract_ref = assemble_device_contract_ref_hex_str(efc_cm_hex_str, manufacturer_id_hex_str, equipment_class_hex_str)
        master_keys_by_device_contract_ref[device_contract_ref]
        # get_master_keys_through_device_contract_data(efc_cm_hex_str, manufacturer_id_hex_str, equipment_class_hex_str)
    except KeyError:
        # Try to get masterkeys through EFC-CM only!!
        # Be careful if there are repeated EFC-CMs for different device models!!
        return get_master_keys_with_efc_cm_only(efc_cm_hex_str)

    return master_keys_by_device_contract_ref[device_contract_ref]

def get_master_keys_with_efc_cm_only(efc_cm_hex_str: str):
    """No device model provided, only an EFC-CM for the current Toll Domain!!"""
    global master_keys_by_device_contract_ref
    efc_cm_hex_str = efc_cm_hex_str.upper()
    for device_contract_ref, master_keys in master_keys_by_device_contract_ref.items():
        if device_contract_ref[0:12] == efc_cm_hex_str:
            return master_keys
    raise TollDomainException(f'Master Keys not found for EFC-CM {efc_cm_hex_str}!!!')

def get_master_keys_with_device_model_only(device_model_name: str):
    """No EFC-CM provided, only a device model name for the current Toll Domain!!"""
    global master_keys_by_device_contract_ref
    master_keyset_names_by_efc_cm = {}
    try:
        device_equipment_ref_list = equipment_refs_by_device_names[device_model_name]
    except KeyError:
        raise TollDomainException(f'Master Keys not found for device model with name {device_model_name}!!!')
    for device_contract_ref, master_keys in master_keys_by_device_contract_ref.items():
        equipment_reference = device_contract_ref[12:20]

        # Found a keyset for the given device model in the current Toll Domain!!
        if equipment_reference in device_equipment_ref_list:
            efc_cm = device_contract_ref[0:12]
            master_keyset_names_by_efc_cm[efc_cm] = master_keys
    if not master_keyset_names_by_efc_cm:
        raise TollDomainException(f'Master Keys not found for device model with name {device_model_name}!!!')
    return master_keyset_names_by_efc_cm


def triple_des_decryption(ciphertext_hex:str, key_hex: str) -> str:
    key_bytes = bytes.fromhex(key_hex)
    cipher = DES3.new(key_bytes, DES3.MODE_ECB)

    # We convert the ciphertext from hex to bytes
    ciphertext_bytes = bytes.fromhex(ciphertext_hex)

    # Decrypt the ciphertext to plaintext
    plaintext_bytes = cipher.decrypt(ciphertext_bytes)
    plaintext_hex = plaintext_bytes.hex().upper()
    return plaintext_hex

def triple_des_encryption(plaintext_hex:str, key_hex: str) -> str:
    key_bytes = bytes.fromhex(key_hex)
    cipher = DES3.new(key_bytes, DES3.MODE_ECB)

    # We convert the plaintext from hex to bytes
    plaintext_bytes = bytes.fromhex(plaintext_hex)

    # Encrypt the plaintext to ciphertext
    ciphertext_bytes = cipher.encrypt(plaintext_bytes)
    ciphertext_hex = ciphertext_bytes.hex().upper()
    return ciphertext_hex

def compute_master_key_kcv(master_key: bytes) -> dict[int, str]:
    return DES3.new(master_key, DES3.MODE_ECB).encrypt(bytearray(8))[:3]

def compute_kcvs_for_efc_cm_keyset(efc_cm: str):
    kcv_dict = {}
    for key_ref, master_key in get_master_keys_with_efc_cm_only(efc_cm).items():
        kcv_dict[key_ref] = compute_master_key_kcv(bytes.fromhex(master_key)).hex().upper()
    return kcv_dict

def get_master_key_with_key_ref_and_efc_cm_only(efc_cm:str, key_ref:str):
    # In case key_ref is passed as an int instead of string...
    key_ref = str(key_ref)
    efc_cm = efc_cm.upper()
    key_derivation_logger.debug(f"Getting the Master Key with ref {key_ref} for EFC-CM {efc_cm}")
    try :
        master_key_bytes = bytes.fromhex(get_master_keys_with_efc_cm_only(efc_cm)[key_ref])
    except KeyError as e:
        key_derivation_logger.error(e)
        key_derivation_logger.error(f"We do not possess the masterkeys for EFC-CM {efc_cm}")
        key_derivation_logger.info(f"Please note: TIS instances have security level 0. They are thus not really protected and can be read freely.")
        raise(e)
    key_derivation_logger.debug("Preparing the 3DES cipher with the provided Master Key")
    return master_key_bytes

# def prepare_3DES_cipher_from_efc_cm(efc_cm:str, key_ref:str):
#     # In case key_ref is passed as an int instead of string...
#     key_ref = str(key_ref)
#     efc_cm = efc_cm.upper()
#     key_derivation_logger.debug(f"Getting the Master Key with ref {key_ref} for EFC-CM {efc_cm}")
#     try :
#         master_access_key = bytes.fromhex(get_master_keys_with_efc_cm_only(efc_cm)[key_ref])
#     except KeyError as e:
#         key_derivation_logger.error(e)
#         key_derivation_logger.error(f"We do not possess the masterkeys for EFC-CM {efc_cm}")
#         key_derivation_logger.info(f"Please note: TIS instances have security level 0. They are thus not really protected and can be read freely.")
#         raise(e)
#     key_derivation_logger.debug("Preparing the 3DES cipher with the provided Master Key")
#     cipher = DES3.new(master_access_key, DES3.MODE_ECB)
#     return cipher

# CODE FOR DERIVED ACCESS KEY (Uses MasterKey with ref 120)
def compute_ack(ac_cr_key_ref:int, mack_bytes:bytes):
    cipher = DES3.new(mack_bytes, DES3.MODE_ECB)

    # We concatenate the AC_CR-KeyReference 4 times to get 8 bytes
    plaintext_hex = ac_cr_key_ref.to_bytes(2, 'big') * 4
    key_derivation_logger.debug(f"Plaintext in hex: 0x{plaintext_hex.hex().upper()}")

    # Compute the Access Key
    access_key = cipher.encrypt(plaintext_hex)
    key_derivation_logger.debug(f"Access Key in hex: {access_key.hex().upper()}")

    return access_key

def decrypt_ack(access_key: bytes, mack_bytes:bytes):
    # key_derivation_logger.debug("Preparing the Master Access Key (MAcK) 3DES cipher")
    # cipher = prepare_3DES_cipher_from_efc_cm(efc_cm, '120')    
    cipher = DES3.new(mack_bytes, DES3.MODE_ECB)

    decrypted_ack_plaintext = cipher.decrypt(access_key)
    key_derivation_logger.info(f"Ack plaintext (decrypted) in hex: {decrypted_ack_plaintext.hex().upper()}")
    return decrypted_ack_plaintext

def compute_ack_with_efc_cm_only(efc_cm:str, ac_cr_key_ref:int):
    key_derivation_logger.debug("Preparing the Master Access Key (MAcK) 3DES cipher")

    # cipher = prepare_3DES_cipher_from_efc_cm(efc_cm, '120')
    mack_bytes = get_master_key_with_key_ref_and_efc_cm_only(efc_cm, '120')
    access_key = compute_ack(ac_cr_key_ref, mack_bytes)
    
    return access_key

def decrypt_ack_with_efc_cm_only(efc_cm:str, access_key:bytes):
    key_derivation_logger.debug("Preparing the Master Access Key (MAcK) 3DES cipher")
    # cipher = prepare_3DES_cipher_from_efc_cm(efc_cm, '120')
    mack_bytes = get_master_key_with_key_ref_and_efc_cm_only(efc_cm, '120')
    
    cipher = DES3.new(mack_bytes, DES3.MODE_ECB)

    decrypted_ack_plaintext = cipher.decrypt(access_key)
    key_derivation_logger.info(f"Plaintext (decrypted access key) in hex: {decrypted_ack_plaintext.hex().upper()}")
    return decrypted_ack_plaintext

def compute_access_credentials(efc_cm:str, rnd_obe:int, ac_cr_key_ref:int):
    # Compute the Access Key
    access_key = compute_ack_with_efc_cm_only(efc_cm, ac_cr_key_ref)
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

def compute_authenticator_with_auk_value(attribute_list_bytes, rnd_rse, auk_value:bytes):
    # Prepare the DES cipher with the MAuK
    cipher = DES.new(auk_value, DES.MODE_ECB)
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

    attr_authenticator = des_output[0:4]
    return attr_authenticator

def compute_authenticator_with_auk_ref(pan_bytes:bytes, efc_cm, attribute_list_bytes, rnd_rse, auk_ref=115) -> bytes:
    # Remember to set the key derivation settings for the Toll Domain!!
    # 2 key derivation algorithms are implemented.
    # One follows EN15509, and the other works for TIS.

    authenticator_key = compute_auk_with_key_ref_and_efc_cm(pan_bytes, efc_cm, auk_ref)

    attr_authenticator = compute_authenticator_with_auk_value(attribute_list_bytes, rnd_rse, auk_value=authenticator_key)
    key_derivation_logger.info(f"[OBE AUTH] Authenticator computed by RSE (UPER hex): {attr_authenticator.hex().upper()}")
    return attr_authenticator

# def decrypt_auth_key(efc_cm, auth_key:bytes, auk_ref=115):
#     key_derivation_logger.debug("Preparing the Master Authentication Key (MAuK) 3DES cipher")
#     cipher = prepare_3DES_cipher_from_efc_cm(efc_cm, auk_ref)

#     decrypted_auth_key = cipher.decrypt(auth_key)
#     key_derivation_logger.info(f"Plaintext (decrypted authentication key) in hex: {decrypted_auth_key.hex().upper()}")
#     return decrypted_auth_key

# Compact_PAN is defined in EN 15509
# CODE FOR DERIVED AUTHENTICATION KEYS (Uses MasterKeys with ref 111 through 118)
def compute_pan_8_msb(pan_bytes:bytes) -> bytes:
    if current_security_profile == 'TIS_decimal':
        return compute_pan_8_msb_tis(pan_bytes)
    elif current_security_profile == 'EN15509':
        pan_8_msb = pan_bytes[0:8]
        return pan_8_msb

def compute_pan_8_msb_tis(pan_bytes:bytes) -> bytes:
    # Weird TIS 8 PAN MSB
    # The literal PAN here is treated as a decimal value, not HEX!!

    # pan_8_msb_tis = int(pan_bytes[0:4].hex()).to_bytes(4) + int(pan_bytes[4:8].hex()).to_bytes(4)
    # pan_8_msb_tis = bytes.fromhex(f'{high_cpan_int:08d}') + bytes.fromhex(f'{low_cpan_int:08d}')
    # pan_8_msb_tis = bytes.fromhex(f'{pan_8_msb_tis.hex().upper()}')
    high_cpan_int = int(pan_bytes[0:4].hex(), 10)
    low_cpan_int = int(pan_bytes[4:8].hex(), 10)

    high_cpan_bytes = high_cpan_int.to_bytes(4)
    low_cpan_bytes = low_cpan_int.to_bytes(4)
    pan_8_msb_tis = high_cpan_bytes + low_cpan_bytes

    return pan_8_msb_tis

def compute_compact_pan(pan_bytes:bytes) -> bytes:
    # Compute actual PAN 8 MSB.
    # This means you can directly pass pan_bytes to the functions without an issue!
    pan_8_msb = compute_pan_8_msb(pan_bytes=pan_bytes)
    if type(pan_8_msb) != bytes:
        raise ValueError('pan_8_msb should be a bytes object!!!')
    if len(pan_8_msb) < 8:
        raise ValueError('pan_8_msb should be at least 8 bytes in length!!!')

    compact_pan_bytes = bytearray()
    for i in range(0,4):
        current_byte = pan_8_msb[i] ^ pan_8_msb[i+4]
        compact_pan_bytes.append(current_byte)

    if current_security_profile == 'TIS_decimal':
        # We interpret a decimal as a hex!
        compact_pan_int = int.from_bytes(compact_pan_bytes)
        return bytes.fromhex(f'{compact_pan_int:08d}')

    elif current_security_profile == 'EN15509':
        pass
    return compact_pan_bytes

# def contract_provider_hex_str_to_iso3166_numeric(contract_provider:str) -> int:
#     # first_5bits = (country_code >> 11) & 0b11111
#     # second_5bits = (country_code >> 6) & 0b11111
#     iso3166_alpha2 = custom_its_per_decoders.decode_baudot_country_code(contract_provider)
#     iso3166_numeric3_dec_str = iso3166.countries_by_alpha2.get(iso3166_alpha2).numeric

def compute_auk_plaintext_contract_provider_part(efc_cm:str) -> bytes:
    contract_provider_hex = efc_cm[0:6]

    # Weird Contract Provider (2 issues):
    # Country code is in 10 bits with Numeric-3 instead
    # of Alpha-2 Country Code encoded with Baudot on ITA2 mode
    # For example, FR in ITA2 is 0b10110 (F) 010100 (R) (0xB2 80 in hex, since LSB is to the left)
    # But TIS uses 0x25 00 instead!!! Which comes from the Numeric-3 country code for France (250), but in hex, not in dec!!!
    # As you can clearly see, this does not follow the EN15509 norm for European Interoperability!!
    #
    # And the IssuerId for Axxès is 0x31 (49 in decimal).
    # TIS uses 0x49 = 73 in dec instead!!!
    #
    # So the ContractProvider is 0x25 00 49 instead of 0xB2 80 31!!!
    if current_security_profile == 'TIS_decimal':
        iso3166_alpha2 = custom_its_per_decoders.decode_baudot_country_code(efc_cm)
        iso3166_numeric3_dec_str = iso3166.countries_by_alpha2.get(iso3166_alpha2).numeric

        # IssuerId is 14 bits long
        issuer_id = int(contract_provider_hex[3:6], 16) & 0x3FFF
        decimal_contract_provider = f'{iso3166_numeric3_dec_str}0{issuer_id:02d}'

        plaintext_extension = decimal_contract_provider + "00"

    elif current_security_profile == 'EN15509':
        plaintext_extension = contract_provider_hex + "00"
        contract_provider_size = len(contract_provider_hex)
        if contract_provider_size != 6:
            key_derivation_logger.error(f"Contract Provider should contain 6 hex characters (3 bytes), not {contract_provider_size} chars!")
    bytes_plaintext_tail = bytes.fromhex(plaintext_extension)
    return bytes_plaintext_tail

def compute_auk_plaintext(pan_bytes:bytes, efc_cm:str) -> bytes:
    key_derivation_logger.debug(f'Computing AuK plaintext for PAN 0x{pan_bytes.hex().upper()} and EFC-CM 0x{efc_cm}...')
    # Prepare the compact PAN
    bytes_compact_pan = compute_compact_pan(pan_bytes)
    # key_derivation_logger.debug(f'Compact PAN in hex: {bytes_compact_pan.hex().upper()}')
    if len(bytes_compact_pan) != 4:
        key_derivation_logger.error("Compact PAN should be encoded in 4 bytes!")

    # Concatenating a "00" tail and assembling the full AuK plaintext
    contract_provider_part = compute_auk_plaintext_contract_provider_part(efc_cm)

    plaintext_bytes = bytes_compact_pan + contract_provider_part
    if len(plaintext_bytes) != 8:
        key_derivation_logger.error("Plaintext should be 8 bytes!!")
        key_derivation_logger.error("Please ensure that the Compact PAN is encoded in 4 bytes and that the Contract Provider is 3 bytes!")
    
    key_derivation_logger.debug(f'AuK plaintext in hex: {plaintext_bytes.hex().upper()}')
    return plaintext_bytes

# CODE FOR DERIVED AUTHENTICATION KEY (Uses MasterKeys with ref 111 through 118)
def compute_auk_with_mauk_value_and_plaintext(plaintext_bytes:bytes, master_key: bytes):
    # Prepare/configure the cipher with the master authentication key (MAuK)
    cipher = DES3.new(master_key, DES3.MODE_ECB)
    
    auth_key = cipher.encrypt(plaintext_bytes)

    key_derivation_logger.debug(f'Computed Auth Key: {auth_key.hex().upper()}')
    return auth_key

def compute_auk(pan_8_msb: bytes, efc_cm: str, mauk_bytes: bytes) -> bytes:
    plaintext_bytes = compute_auk_plaintext(pan_8_msb, efc_cm=efc_cm)

    # key_derivation_logger.info(f'FOUND MAUK: 0x{mauk_hex}')
    return compute_auk_with_mauk_value_and_plaintext(plaintext_bytes, mauk_bytes)

def decrypt_auk(auth_key:bytes, mauk_bytes: bytes):
    cipher = DES3.new(mauk_bytes, DES3.MODE_ECB)

    decrypted_auth_key = cipher.decrypt(auth_key)
    key_derivation_logger.info(f"AuK plaintext (decryption) in hex: {decrypted_auth_key.hex().upper()}")
    return decrypted_auth_key

def compute_auk_with_key_ref_and_efc_cm(pan_8_msb: bytes, efc_cm: str, key_ref:int=115) -> bytes:
    # key_derivation_logger.debug(f'Computing Authentication Key with KeyRef {key_ref} for PAN {pan_8_msb}...')
    # key_derivation_logger.debug(f'Getting the Contract Provider for EFC-CM 0x{efc_cm}. It is encodeed in the first 3 bytes of the EFC-CM...')
    plaintext_bytes = compute_auk_plaintext(pan_8_msb, efc_cm=efc_cm)

    if key_ref not in range(111, 119):
        raise ValueError("Invalid master authentication key (MAuK) reference!")
    mauk_hex = get_master_keys_with_efc_cm_only(efc_cm)[str(key_ref)]
    mauk = bytes.fromhex(mauk_hex)
    # key_derivation_logger.info(f'FOUND MAUK: 0x{mauk_hex}')
    return compute_auk_with_mauk_value_and_plaintext(plaintext_bytes, mauk)

def compute_all_auth_keys(pan_8_msb: bytes, efc_cm: str, mauk_hex_dict: dict) -> dict[int, bytes]:
    key_derivation_logger.debug(f'Computing all 8 Authentication Keys for PAN {pan_8_msb}')
    key_derivation_logger.debug(f'Getting the Contract Provider. It is encodeed in the first 3 bytes of the EFC-CM...')
    plaintext_bytes = compute_auk_plaintext(pan_8_msb, efc_cm)
    
    auth_keys = {}
    for key_ref in range(111, 119):
        mauk_hex = mauk_hex_dict[str(key_ref)]
        mauk = bytes.fromhex(mauk_hex)
        auth_keys[key_ref] = compute_auk_with_mauk_value_and_plaintext(plaintext_bytes, mauk)
    return auth_keys

def compute_all_auth_keys_with_efc_cm_only(pan_8_msb: bytes, efc_cm: str) -> dict[int, bytes]:
    plaintext_bytes = compute_auk_plaintext(pan_8_msb, efc_cm)
    
    mauk_hex_dict = get_master_keys_with_efc_cm_only(efc_cm)
    return compute_all_auth_keys(pan_8_msb, efc_cm, mauk_hex_dict)

def compute_all_auth_keys_and_return_hex_dict(pan_8_msb:bytes, efc_cm:str):
    auth_keys_dict = compute_all_auth_keys_with_efc_cm_only(pan_8_msb, efc_cm)
    return {key_ref: computed_auk.hex().upper() for (key_ref, computed_auk) in auth_keys_dict.items()}

# COMPUTE ALL DERIVED KEYS
def compute_all_derived_keys(pan_8_msb:bytes, efc_cm:str, ac_cr_key_ref:int, master_keys:dict):
    derived_keys_dict = compute_all_auth_keys(pan_8_msb, efc_cm, master_keys)
    mack_bytes = bytes.fromhex(master_keys['120'])
    derived_keys_dict[120] = compute_ack(ac_cr_key_ref, mack_bytes)
    return derived_keys_dict

def compute_all_derived_keys_and_return_hex_dict(pan_8_msb:bytes, efc_cm:str, ac_cr_key_ref:int, master_keys:dict):
    derived_keys_dict = compute_all_derived_keys(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)
    return {key_ref: computed_auk.hex().upper() for (key_ref, computed_auk) in derived_keys_dict.items()}

def compute_all_derived_keys_for_efc_cm_and_return_hex_dict(pan_8_msb:bytes, efc_cm:str, ac_cr_key_ref:int):
    master_keys = get_master_keys_with_efc_cm_only(efc_cm)
    return compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)

def compute_all_derived_keys_for_device_model(pan_8_msb:bytes, device_model_name:str, ac_cr_key_ref:int):
    efc_cm_to_derived_keys = {}
    master_keys_by_efc_cm = get_master_keys_with_device_model_only(device_model_name)
    for efc_cm, master_keys in master_keys_by_efc_cm.items():
        efc_cm_to_derived_keys[efc_cm] = compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)
        # derived_keys_dict = compute_all_auth_keys(pan_8_msb, efc_cm, master_keys)
        # derived_keys_dict[120] = compute_ack(efc_cm, ac_cr_key_ref, master_keys['120'])
        # efc_cm_to_derived_keys[efc_cm] = {key_ref: computed_auk.hex().upper() for (key_ref, computed_auk) in derived_keys_dict.items()}
    return efc_cm_to_derived_keys

def compute_all_derived_keys_for_available_keysets_and_return_hex_dict(pan_8_msb:bytes, ac_cr_key_ref:int):
    efc_cm_to_derived_keys = {}
    for efc_cm, master_keys in master_keys_by_device_contract_ref.items():
        derived_keys_hex_dict = compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)
        efc_cm_to_derived_keys[efc_cm] = derived_keys_hex_dict
    return efc_cm_to_derived_keys

# def compute_all_derived_keys_for_available_keysets_and_return_hex_dict(pan_8_msb:bytes, ac_cr_key_ref:int):
#     efc_cm_to_derived_keys = {}
#     for efc_cm in master_keys_by_device_contract_ref:
#         derived_keys_dict = compute_all_auth_keys_with_efc_cm_only(pan_8_msb, efc_cm)
#         derived_keys_dict[120] = compute_ack_with_efc_cm_only(efc_cm, ac_cr_key_ref)
#         efc_cm_to_derived_keys[efc_cm] = {key_ref: computed_auk.hex().upper() for (key_ref, computed_auk) in derived_keys_dict.items()}
#     return efc_cm_to_derived_keys

def decipher_auth_key_with_mauk_value(auth_key: str, mauk: str) -> bytes:
    bytes_master_key = bytes.fromhex(mauk)
    # Prepare/configure the cipher with the master key
    cipher = DES3.new(bytes_master_key, DES3.MODE_ECB)

    # Decipher
    deciphered_plaintext_bytes = cipher.decrypt(bytes.fromhex(auth_key))

    return deciphered_plaintext_bytes

def decipher_auth_key_with_efc_cm_and_mauk_ref_(auth_key: str, efc_cm: str, key_ref: int) -> bytes:
    mauk = get_master_keys_with_efc_cm_only(efc_cm)[str(key_ref)]
    return decipher_auth_key_with_mauk_value(auth_key, mauk)