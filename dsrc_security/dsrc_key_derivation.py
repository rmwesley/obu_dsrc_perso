import os
import json
import iso3166
import custom_its_per_decoders

from Crypto.Cipher import DES3
from Crypto.Cipher import DES

import logging
import dsrc_security.dsrc_mk_by_device_and_td_loader as dsrc_mk_by_device_and_td_loader

key_derivation_logger = logging.getLogger(__name__)

from ASN.compiled_DSRC_instances import EFCv10_1 as EFC

# Loading the Master Keys from a JSON into a Python dict
# This dict maps an EFC-CM in hex format to a MasterKeySet also in hex format
try:
    os.environ['EFC_SEC_CONF_PATH']
except:
    os.environ['EFC_SEC_CONF_PATH'] = r"..\efc_security_config_v2.2.3.json"

efc_sec_conf_path = os.environ['EFC_SEC_CONF_PATH']

master_keys_by_toll_domain = dsrc_mk_by_device_and_td_loader.load_master_keys_by_toll_domain()

class TollDomainSecurityProfileInvalidException(Exception):
    pass

def _force_set_security_profile(security_profile:str):
    global current_security_profile
    if security_profile not in ['TIS_decimal', 'EN15509']:
        raise TollDomainSecurityProfileInvalidException('The only valid security profile options are (TIS_decimal) or (EN15509)')
    current_security_profile = security_profile

def update_security_profile():
    global current_security_profile
    current_security_profile = dsrc_mk_by_device_and_td_loader.get_current_security_profile()

update_security_profile()

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

def compute_kcvs_for_hex_master_keyset(master_key_hex_dict:dict):
    kcv_dict = {}
    for key_ref, master_key in master_key_hex_dict.items():
        kcv_dict[key_ref] = compute_master_key_kcv(bytes.fromhex(master_key)).hex().upper()
    return kcv_dict

def compute_kcvs_for_all_keysets():
    keysets_kcvs_dict = {}
    master_keysets = dsrc_mk_by_device_and_td_loader.get_all_master_keysets()
    for keyset_name, master_key_hex_dict in master_keysets.items():
        keysets_kcvs_dict[keyset_name] = compute_kcvs_for_hex_master_keyset(master_key_hex_dict)
    return keysets_kcvs_dict

def compute_kcvs_for_efc_cm_keyset(efc_cm: str):
    master_key_hex_dict = dsrc_mk_by_device_and_td_loader.get_master_keys_with_efc_cm_only(efc_cm)
    return compute_kcvs_for_hex_master_keyset(master_key_hex_dict)

def get_master_key_with_key_ref_and_efc_cm_only(efc_cm:str, key_ref:str):
    # In case key_ref is passed as an int instead of string...
    key_ref = str(key_ref)
    efc_cm = efc_cm.upper()
    key_derivation_logger.debug(f"Getting the Master Key with ref {key_ref} for EFC-CM {efc_cm}")
    try :
        master_key_bytes = bytes.fromhex(dsrc_mk_by_device_and_td_loader.get_master_keys_with_efc_cm_only(efc_cm)[key_ref])
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

# Compact_PAN is defined in EN 15509
# CODE FOR DERIVED AUTHENTICATION KEYS (Uses MasterKeys with ref 111 through 118)
def compute_pan_8_msb(pan_bytes:bytes) -> bytes:
    global current_security_profile
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
    master_hex_keyset = dsrc_mk_by_device_and_td_loader.get_master_keys_with_efc_cm_only(efc_cm)
    mauk_hex = master_hex_keyset[str(key_ref)]
    mauk_bytes = bytes.fromhex(mauk_hex)
    # key_derivation_logger.info(f'FOUND MAUK: 0x{mauk_hex}')
    return compute_auk_with_mauk_value_and_plaintext(plaintext_bytes, mauk_bytes)

def decrypt_auk_with_key_ref_and_efc_cm(auth_key:bytes, efc_cm, auk_ref=115):
    if auk_ref not in range(111, 119):
        raise ValueError("Invalid master authentication key (MAuK) reference!")
    master_hex_keyset = dsrc_mk_by_device_and_td_loader.get_master_keys_with_efc_cm_only(efc_cm)
    mauk_hex = master_hex_keyset[str(auk_ref)]
    mauk_bytes = bytes.fromhex(mauk_hex)

    return decrypt_auk(auth_key=auth_key, mauk_bytes=mauk_bytes)

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
    
    mauk_hex_dict = dsrc_mk_by_device_and_td_loader.get_master_keys_with_efc_cm_only(efc_cm)
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
    master_keys = dsrc_mk_by_device_and_td_loader.get_master_keys_with_efc_cm_only(efc_cm)
    return compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)

def compute_all_derived_keys_for_device_model(pan_8_msb:bytes, device_model_name:str, ac_cr_key_ref:int):
    efc_cm_to_derived_keys = {}
    master_keys_by_efc_cm = dsrc_mk_by_device_and_td_loader.get_master_keys_with_device_model_only(device_model_name)
    for efc_cm, master_keys in master_keys_by_efc_cm.items():
        efc_cm_to_derived_keys[efc_cm] = compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)
        # derived_keys_dict = compute_all_auth_keys(pan_8_msb, efc_cm, master_keys)
        # derived_keys_dict[120] = compute_ack(efc_cm, ac_cr_key_ref, master_keys['120'])
        # efc_cm_to_derived_keys[efc_cm] = {key_ref: computed_auk.hex().upper() for (key_ref, computed_auk) in derived_keys_dict.items()}
    return efc_cm_to_derived_keys

def compute_all_derived_keys_by_device_contract_ref(pan_8_msb:bytes, ac_cr_key_ref:int):
    derived_keys_by_device_contract_ref = {}
    for device_contract_ref, master_keys in dsrc_mk_by_device_and_td_loader.master_keys_by_device_contract_ref.items():
        efc_cm = device_contract_ref[0:12]

        derived_keys_hex_dict = compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)
        derived_keys_by_device_contract_ref[device_contract_ref] = derived_keys_hex_dict
    return derived_keys_by_device_contract_ref

def compute_all_derived_keys_by_keyset_name(pan_8_msb:bytes, efc_cm:str, ac_cr_key_ref:int):
    derived_keys_by_keyset_name = {}
    all_master_keysets = dsrc_mk_by_device_and_td_loader.get_all_master_keysets()

    for keyset_name, master_keys_hex_dict in all_master_keysets:
        derived_keys_hex_dict = compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys_hex_dict)
        derived_keys_by_keyset_name[keyset_name] = derived_keys_hex_dict
    return derived_keys_by_keyset_name

def decipher_auth_key_with_mauk_value(auth_key: str, mauk: str) -> bytes:
    bytes_master_key = bytes.fromhex(mauk)
    # Prepare/configure the cipher with the master key
    cipher = DES3.new(bytes_master_key, DES3.MODE_ECB)

    # Decipher
    deciphered_plaintext_bytes = cipher.decrypt(bytes.fromhex(auth_key))

    return deciphered_plaintext_bytes

def decipher_auth_key_with_efc_cm_and_mauk_ref_(auth_key: str, efc_cm: str, key_ref: int) -> bytes:
    mauk = dsrc_mk_by_device_and_td_loader.get_master_keys_with_efc_cm_only(efc_cm)[str(key_ref)]
    return decipher_auth_key_with_mauk_value(auth_key, mauk)