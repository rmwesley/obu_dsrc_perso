import os
import iso3166
import custom_its_per_decoders

from Crypto.Cipher import DES3

import logging
from dsrc_security import dsrc_td_security_operations

key_derivation_logger = logging.getLogger(__name__)

class UnknownTdSecurityProfile(Exception):
    pass
class UnconfiguredTdSecurityProfile(Exception):
    pass
class InvalidAuthKeyRef(ValueError):
    pass

# If you ever want to implement handling of a new security profile, remember to update the following methods:
# 1 - .compute_pan_8_msb()
# These profiles (EN15509 and the custom "TIS decimal") are all in fact based on EN15509 (levels 0 and 1).
AVAILBLE_SECURITY_PROFILES = ['TIS_decimal_level_0', 'TIS_decimal_level_1', 'EN15509_level_0', 'EN15509_level_1']
def _force_set_security_profile(security_profile:str):
    global current_security_profile
    if security_profile not in AVAILBLE_SECURITY_PROFILES:
        raise UnknownTdSecurityProfile(f'The security profile options are: {AVAILBLE_SECURITY_PROFILES}')
    current_security_profile = security_profile

def update_security_profile():
    global current_security_profile
    current_security_profile = dsrc_td_security_operations.get_current_security_profile()

    if current_security_profile not in AVAILBLE_SECURITY_PROFILES:
        raise UnknownTdSecurityProfile(f'The security profile options are: {AVAILBLE_SECURITY_PROFILES}')

update_security_profile()

def is_en15509(td_security_profile_name: str):
    return td_security_profile_name == 'EN15509_level_0' or td_security_profile_name == 'EN15509_level_1'

def is_tis_decimal(td_security_profile_name: str):
    return td_security_profile_name == 'TIS_decimal_level_0' or td_security_profile_name == 'TIS_decimal_level_1'

def compute_master_key_kcv(master_key: bytes) -> dict[int, str]:
    return DES3.new(master_key, DES3.MODE_ECB).encrypt(bytearray(8))[:3]

def compute_kcvs_for_hex_master_keyset(master_key_hex_dict:dict):
    kcv_dict = {}
    for key_ref, master_key in master_key_hex_dict.items():
        kcv_dict[key_ref] = compute_master_key_kcv(bytes.fromhex(master_key)).hex().upper()
    return kcv_dict

def compute_kcvs_for_all_keysets():
    keysets_kcvs_dict = {}
    master_keysets = dsrc_td_security_operations.get_all_master_keysets()
    for keyset_name, master_key_hex_dict in master_keysets.items():
        keysets_kcvs_dict[keyset_name] = compute_kcvs_for_hex_master_keyset(master_key_hex_dict)
    return keysets_kcvs_dict

def compute_kcvs_for_efc_cm_keyset(efc_cm: str):
    master_key_hex_dict = dsrc_td_security_operations.get_master_keys_with_efc_cm_only(efc_cm)
    return compute_kcvs_for_hex_master_keyset(master_key_hex_dict)

def get_master_key_with_key_ref_and_efc_cm_only(efc_cm:str, key_ref:str):
    # In case key_ref is passed as an int instead of string...
    key_ref = str(key_ref)
    efc_cm = efc_cm.upper()
    key_derivation_logger.debug(f"Getting the Master Key with ref {key_ref} for EFC-CM {efc_cm}")
    try :
        master_key_bytes = bytes.fromhex(dsrc_td_security_operations.get_master_keys_with_efc_cm_only(efc_cm)[key_ref])
    except KeyError as e:
        key_derivation_logger.error(e)
        key_derivation_logger.error(f"We do not possess the masterkeys for EFC-CM {efc_cm}")
        key_derivation_logger.info(f"Please note: TIS instances have security level 0. They are thus not really protected and can be read freely.")
        raise(e)
    key_derivation_logger.debug("Preparing the 3DES cipher with the provided Master Key")
    return master_key_bytes

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
    cipher = DES3.new(mack_bytes, DES3.MODE_ECB)

    decrypted_ack_plaintext = cipher.decrypt(access_key)
    key_derivation_logger.info(f"Ack plaintext (decrypted) in hex: {decrypted_ack_plaintext.hex().upper()}")
    return decrypted_ack_plaintext

def compute_ack_with_efc_cm_only(efc_cm:str, ac_cr_key_ref:int):
    key_derivation_logger.debug("Preparing the Master Access Key (MAcK) 3DES cipher")

    mack_bytes = get_master_key_with_key_ref_and_efc_cm_only(efc_cm, '120')
    access_key = compute_ack(ac_cr_key_ref, mack_bytes)
    
    return access_key

def decrypt_ack_with_efc_cm_only(efc_cm:str, access_key:bytes):
    key_derivation_logger.debug("Preparing the Master Access Key (MAcK) 3DES cipher")

    mack_bytes = get_master_key_with_key_ref_and_efc_cm_only(efc_cm, '120')
    
    cipher = DES3.new(mack_bytes, DES3.MODE_ECB)

    decrypted_ack_plaintext = cipher.decrypt(access_key)
    key_derivation_logger.info(f"Plaintext (decrypted access key) in hex: {decrypted_ack_plaintext.hex().upper()}")
    return decrypted_ack_plaintext

# Compact_PAN is defined in EN 15509
# CODE FOR DERIVED AUTHENTICATION KEYS (Uses MasterKeys with ref 111 through 118)
def compute_pan_8_msb(pan_bytes:bytes) -> bytes:
    global current_security_profile
    if is_tis_decimal(current_security_profile):
        return tis_compute_pan_8_msb(pan_bytes)
    if is_en15509(current_security_profile):
        return en15509_compute_pan_8_msb(pan_bytes)
    else:
        raise UnconfiguredTdSecurityProfile(f"Please properly update the methods for handling the current security profile ({current_security_profile})")

def en15509_compute_pan_8_msb(pan_bytes:bytes) -> bytes:
    pan_8_msb = pan_bytes[0:8]
    return pan_8_msb

def tis_compute_pan_8_msb(pan_bytes:bytes) -> bytes:
    # Weird TIS 8 PAN MSB
    # The literal PAN here is treated as a decimal value, not HEX!!

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
    if not isinstance(pan_8_msb, bytes):
        raise ValueError('pan_8_msb should be a bytes object!!!')
    if len(pan_8_msb) < 8:
        raise ValueError('pan_8_msb should be at least 8 bytes in length!!!')

    compact_pan_bytes = bytearray()
    for i in range(0,4):
        current_byte = pan_8_msb[i] ^ pan_8_msb[i+4]
        compact_pan_bytes.append(current_byte)

    if 'TIS_decimal' in current_security_profile:
        # We interpret a decimal as a hex!
        compact_pan_int = int.from_bytes(compact_pan_bytes)
        return bytes.fromhex(f'{compact_pan_int:08d}')

    elif 'EN15509' in current_security_profile:
        pass
    return compact_pan_bytes

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
    if 'TIS_decimal' in current_security_profile:
        iso3166_alpha2 = custom_its_per_decoders.decode_baudot_country_code(efc_cm)
        iso3166_numeric3_dec_str = iso3166.countries_by_alpha2.get(iso3166_alpha2).numeric

        # IssuerId is 14 bits long
        issuer_id = int(contract_provider_hex[3:6], 16) & 0x3FFF
        decimal_contract_provider = f'{iso3166_numeric3_dec_str}0{issuer_id:02d}'

        plaintext_extension = decimal_contract_provider + "00"

    elif 'EN15509' in current_security_profile:
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

def compute_auk_with_device_info_and_auk_ref(pan_8_msb: bytes, efc_cm_hex_str: str, manufacturer_id_hex_str:str, equipment_class_hex_str: str, auk_ref:int=115) -> bytes:
    # key_derivation_logger.debug(f'Computing Authentication Key with KeyRef {auk_ref} for PAN {pan_8_msb}...')
    # key_derivation_logger.debug(f'Getting the Contract Provider for EFC-CM 0x{efc_cm}. It is encodeed in the first 3 bytes of the EFC-CM...')
    if auk_ref not in range(111, 119):
        raise InvalidAuthKeyRef("Invalid master authentication key (MAuK) reference!")

    plaintext_bytes = compute_auk_plaintext(pan_8_msb, efc_cm=efc_cm_hex_str)

    master_hex_keyset = dsrc_td_security_operations.get_master_keys_with_device_info_in_current_td(efc_cm_hex_str, manufacturer_id_hex_str, equipment_class_hex_str)
    mauk_hex = master_hex_keyset[str(auk_ref)]
    mauk_bytes = bytes.fromhex(mauk_hex)
    # key_derivation_logger.info(f'FOUND MAuK: 0x{mauk_hex}')
    return compute_auk_with_mauk_value_and_plaintext(plaintext_bytes, mauk_bytes)

def compute_auk_with_device_contract_ref_and_auk_ref(pan_8_msb: bytes, device_contract_ref: str, auk_ref:int=115) -> bytes:
    # key_derivation_logger.debug(f'Computing Authentication Key with KeyRef {auk_ref} for PAN {pan_8_msb}...')
    # key_derivation_logger.debug(f'Getting the Contract Provider for EFC-CM 0x{efc_cm}. It is encodeed in the first 3 bytes of the EFC-CM...')
    if auk_ref not in range(111, 119):
        raise InvalidAuthKeyRef("Invalid master authentication key (MAuK) reference!")

    efc_cm_hex = device_contract_ref[0:12]

    plaintext_bytes = compute_auk_plaintext(pan_8_msb, efc_cm=efc_cm_hex)

    master_hex_keyset = dsrc_td_security_operations.get_master_keys_with_device_contract_ref(device_contract_ref)
    mauk_hex = master_hex_keyset[str(auk_ref)]
    mauk_bytes = bytes.fromhex(mauk_hex)
    # key_derivation_logger.info(f'FOUND MAuK: 0x{mauk_hex}')
    return compute_auk_with_mauk_value_and_plaintext(plaintext_bytes, mauk_bytes)

def compute_auk_with_efc_cm_and_auk_ref(pan_8_msb: bytes, efc_cm: str, auk_ref:int=115) -> bytes:
    # key_derivation_logger.debug(f'Computing Authentication Key with KeyRef {key_ref} for PAN {pan_8_msb}...')
    # key_derivation_logger.debug(f'Getting the Contract Provider for EFC-CM 0x{efc_cm}. It is encodeed in the first 3 bytes of the EFC-CM...')
    if auk_ref not in range(111, 119):
        raise InvalidAuthKeyRef("Invalid master authentication key (MAuK) reference!")

    plaintext_bytes = compute_auk_plaintext(pan_8_msb, efc_cm=efc_cm)

    master_hex_keyset = dsrc_td_security_operations.get_master_keys_with_efc_cm_only(efc_cm)
    mauk_hex = master_hex_keyset[str(auk_ref)]
    mauk_bytes = bytes.fromhex(mauk_hex)
    # key_derivation_logger.info(f'FOUND MAUK: 0x{mauk_hex}')
    return compute_auk_with_mauk_value_and_plaintext(plaintext_bytes, mauk_bytes)

def decrypt_auk_with_efc_cm_and_auk_ref(auth_key:bytes, efc_cm, auk_ref=115):
    if auk_ref not in range(111, 119):
        raise InvalidAuthKeyRef("Invalid master authentication key (MAuK) reference!")
    master_hex_keyset = dsrc_td_security_operations.get_master_keys_with_efc_cm_only(efc_cm)
    mauk_hex = master_hex_keyset[str(auk_ref)]
    mauk_bytes = bytes.fromhex(mauk_hex)

    return decrypt_auk(auth_key=auth_key, mauk_bytes=mauk_bytes)

def compute_all_8_auth_keys(pan_8_msb: bytes, efc_cm: str, mauk_hex_dict: dict) -> dict[int, bytes]:
    key_derivation_logger.debug(f'Computing all 8 Authentication Keys for PAN {pan_8_msb}')
    key_derivation_logger.debug(f'Getting the Contract Provider. It is encodeed in the first 3 bytes of the EFC-CM...')
    plaintext_bytes = compute_auk_plaintext(pan_8_msb, efc_cm)
    
    auth_keys = {}
    for key_ref in range(111, 119):
        mauk_hex = mauk_hex_dict[str(key_ref)]
        mauk = bytes.fromhex(mauk_hex)
        auth_keys[key_ref] = compute_auk_with_mauk_value_and_plaintext(plaintext_bytes, mauk)
    return auth_keys

def compute_all_8_auth_keys_with_efc_cm_only(pan_8_msb: bytes, efc_cm: str) -> dict[int, bytes]:
    plaintext_bytes = compute_auk_plaintext(pan_8_msb, efc_cm)
    
    mauk_hex_dict = dsrc_td_security_operations.get_master_keys_with_efc_cm_only(efc_cm)
    return compute_all_8_auth_keys(pan_8_msb, efc_cm, mauk_hex_dict)

def compute_all_8_auth_keys_and_return_hex_dict(pan_8_msb:bytes, efc_cm:str):
    auth_keys_dict = compute_all_8_auth_keys_with_efc_cm_only(pan_8_msb, efc_cm)
    return {key_ref: computed_auk.hex().upper() for (key_ref, computed_auk) in auth_keys_dict.items()}

# COMPUTE ALL DERIVED KEYS
def compute_all_derived_keys(pan_8_msb:bytes, efc_cm:str, ac_cr_key_ref:int, master_keys:dict):
    derived_keys_dict = compute_all_8_auth_keys(pan_8_msb, efc_cm, master_keys)
    mack_bytes = bytes.fromhex(master_keys['120'])
    derived_keys_dict[120] = compute_ack(ac_cr_key_ref, mack_bytes)
    return derived_keys_dict

def compute_all_derived_keys_and_return_hex_dict(pan_8_msb:bytes, efc_cm:str, ac_cr_key_ref:int, master_keys:dict):
    derived_keys_dict = compute_all_derived_keys(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)
    return {key_ref: computed_auk.hex().upper() for (key_ref, computed_auk) in derived_keys_dict.items()}

def compute_all_derived_keys_for_efc_cm_and_return_hex_dict(pan_8_msb:bytes, efc_cm:str, ac_cr_key_ref:int):
    master_keys = dsrc_td_security_operations.get_master_keys_with_efc_cm_only(efc_cm)
    return compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)

def compute_all_derived_keys_for_device_model(pan_8_msb:bytes, device_model_name:str, ac_cr_key_ref:int):
    efc_cm_to_derived_keys = {}
    master_keys_by_efc_cm = dsrc_td_security_operations.get_master_keys_with_device_model_only(device_model_name)
    for efc_cm, master_keys in master_keys_by_efc_cm.items():
        efc_cm_to_derived_keys[efc_cm] = compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)
    return efc_cm_to_derived_keys

def compute_all_derived_keys_by_device_contract_ref(pan_8_msb:bytes, ac_cr_key_ref:int):
    derived_keys_by_device_contract_ref = {}
    for device_contract_ref, master_keys in dsrc_td_security_operations.master_keys_by_device_contract_ref.items():
        efc_cm = device_contract_ref[0:12]

        derived_keys_hex_dict = compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)
        derived_keys_by_device_contract_ref[device_contract_ref] = derived_keys_hex_dict
    return derived_keys_by_device_contract_ref

def compute_all_derived_keys_by_keyset_name(pan_8_msb:bytes, efc_cm:str, ac_cr_key_ref:int):
    derived_keys_by_keyset_name = {}
    all_master_keysets = dsrc_td_security_operations.get_all_master_keysets()

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

def decipher_auth_key_with_efc_cm_and_auk_ref(auth_key: str, efc_cm: str, auk_ref: int) -> bytes:
    mauk = dsrc_td_security_operations.get_master_keys_with_efc_cm_only(efc_cm)[str(auk_ref)]
    return decipher_auth_key_with_mauk_value(auth_key, mauk)