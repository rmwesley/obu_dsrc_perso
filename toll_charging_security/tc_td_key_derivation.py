import logging

from dsrc_security import dsrc_key_derivation
from toll_charging_security import tc_td_security_operations, tc_manage_toll_domains

tc_key_derivation_logger = logging.getLogger(__name__)

def compute_kcvs_for_all_keysets():
    keysets_kcvs_dict = {}
    master_keysets = get_all_master_keysets()
    for keyset_name, master_key_hex_dict in master_keysets.items():
        keysets_kcvs_dict[keyset_name] = dsrc_key_derivation.compute_kcvs_for_hex_master_keyset(master_key_hex_dict)
    return keysets_kcvs_dict

def compute_kcvs_for_efc_cm_keyset(efc_cm: str):
    master_key_hex_dict = tc_td_security_operations.get_master_keys_with_efc_cm_only_on_td(efc_cm)
    return dsrc_key_derivation.compute_kcvs_for_hex_master_keyset(master_key_hex_dict)

def get_master_key_with_key_ref_and_efc_cm_only(efc_cm:str, key_ref:str):
    # In case key_ref is passed as an int instead of string...
    key_ref = str(key_ref)
    efc_cm = efc_cm.upper()
    tc_key_derivation_logger.debug(f"Getting the Master Key with ref {key_ref} for EFC-CM {efc_cm}")
    try :
        master_key_bytes = bytes.fromhex(tc_td_security_operations.get_master_keys_with_efc_cm_only_on_td(efc_cm)[key_ref])
    except KeyError as e:
        tc_key_derivation_logger.error(e)
        tc_key_derivation_logger.error(f"We do not possess the masterkeys for EFC-CM {efc_cm}")
        tc_key_derivation_logger.info(f"Please note: TIS instances have security level 0. They are thus not really protected and can be read freely.")
        raise(e)
    tc_key_derivation_logger.debug("Preparing the 3DES cipher with the provided Master Key")
    return master_key_bytes

class DsrcKeyDerivationException(ValueError):
    pass
def compute_ack_for_obu_on_td(device_contract_ref:str, ac_cr_key_ref:int, td_name:str):
    master_keys = tc_td_security_operations.get_master_keys_with_obu_contract_ref_on_td(device_contract_ref, td_name)
    mack_hex = master_keys['120']
    mack_bytes = bytes.fromhex(mack_hex)
    try:
        access_key = dsrc_key_derivation.compute_ack_with_mack_bytes(ac_cr_key_ref, mack_bytes)
    except dsrc_key_derivation.TripleDesInitException as e:
        error_msg = f'3DES init exception!! OBU contract is {device_contract_ref}, AC_CR-KeyRef is {ac_cr_key_ref} and TD is {td_name}'
        tc_key_derivation_logger.critical(error_msg)
        raise DsrcKeyDerivationException(error_msg)

    return access_key

def compute_ack_with_efc_cm_only(efc_cm:str, ac_cr_key_ref:int) -> bytes:
    tc_key_derivation_logger.debug("Preparing the Master Access Key (MAcK) 3DES cipher")

    mack_hex = get_master_key_with_key_ref_and_efc_cm_only(efc_cm, '120')
    mack_bytes = bytes.fromhex(mack_hex)
    access_key = dsrc_key_derivation.compute_ack_with_mack_bytes(ac_cr_key_ref, mack_bytes)
    
    return access_key

def decrypt_ack_with_efc_cm_only(efc_cm:str, access_key:bytes):
    tc_key_derivation_logger.debug("Preparing the Master Access Key (MAcK) 3DES cipher")

    mack_bytes = get_master_key_with_key_ref_and_efc_cm_only(efc_cm, '120')

    return dsrc_key_derivation.decrypt_ack_with_mack_bytes(access_key, mack_bytes)

def compute_auk_with_device_contract_ref_auk_ref_on_td(pan_8_msb: bytes, device_contract_ref: str, td_name:str, norm:str, auk_ref:int=115) -> bytes:
    """Get MasterKeys on TD with td_name and compute AuK following the chosen norm!"""
    master_hex_keyset = tc_td_security_operations.get_master_keys_with_obu_contract_ref_on_td(device_contract_ref, td_name)
    mauk_hex = master_hex_keyset[str(auk_ref)]
    mauk_bytes = bytes.fromhex(mauk_hex)

    # key_derivation_logger.info(f'FOUND MAuK: 0x{mauk_hex}')
    return dsrc_key_derivation.compute_auk_with_device_contract_ref_and_mauk_value(pan_8_msb, device_contract_ref, mauk_bytes, norm=norm)

def compute_auk_with_obu_info_and_auk_ref_on_td(
        pan_8_msb: bytes,
        efc_cm_hex_str: str,
        manufacturer_id_hex_str: str,
        equipment_class_hex_str: str,
        norm:str,
        td_name:str,
        auk_ref:int=115,
    ) -> bytes:
    """Get MasterKeys on TD with td_name and compute AuK following the chosen norm!"""
    master_hex_keyset = tc_td_security_operations.get_master_keys_for_obu_on_td(efc_cm_hex_str, manufacturer_id_hex_str, equipment_class_hex_str, td_name)
    mauk_hex = master_hex_keyset[str(auk_ref)]
    mauk_bytes = bytes.fromhex(mauk_hex)

    return dsrc_key_derivation.compute_auk_with_efc_cm_and_mauk_value(pan_8_msb, efc_cm_hex_str, mauk_bytes, norm)

def force_compute_auk_with_efc_cm_and_auk_ref_only(pan_8_msb: bytes, efc_cm: str, auk_ref:int=115, td_name:str='TIS', norm:str='TIS_decimal') -> bytes:
    """
    Lookup a MasterKey through EFC-CM only!
    That is, ignore ManufacturerId and EquipmentClass in MasterKey search.
    """
    plaintext_bytes = dsrc_key_derivation.compute_auk_plaintext(pan_8_msb, efc_cm=efc_cm, norm=norm)

    master_hex_keyset = tc_td_security_operations.get_master_keys_with_efc_cm_only_on_td(efc_cm, td_name)
    mauk_hex = master_hex_keyset[str(auk_ref)]
    mauk_bytes = bytes.fromhex(mauk_hex)
    # key_derivation_logger.info(f'FOUND MAUK: 0x{mauk_hex}')
    return dsrc_key_derivation.compute_auk_with_mauk_value_and_plaintext(plaintext_bytes, mauk_bytes)

def decrypt_auk_with_efc_cm_and_auk_ref(auth_key:bytes, efc_cm, auk_ref=115):
    if auk_ref not in range(111, 119):
        raise dsrc_key_derivation.InvalidAuthKeyRef("Invalid master authentication key (MAuK) reference!")
    master_hex_keyset = tc_td_security_operations.get_master_keys_with_efc_cm_only_on_td(efc_cm)
    mauk_hex = master_hex_keyset[str(auk_ref)]
    mauk_bytes = bytes.fromhex(mauk_hex)

    return dsrc_key_derivation.decrypt_auk(auth_key=auth_key, mauk_bytes=mauk_bytes)

def compute_all_8_auth_keys_with_efc_cm_only(pan_8_msb: bytes, efc_cm: str, norm:str='TIS_decimal') -> dict[int, bytes]:
    plaintext_bytes = dsrc_key_derivation.compute_auk_plaintext(pan_8_msb, efc_cm, norm)
    
    mauk_hex_dict = tc_td_security_operations.get_master_keys_with_efc_cm_only_on_td(efc_cm)
    return dsrc_key_derivation.compute_all_8_auth_keys(pan_8_msb, efc_cm, mauk_hex_dict, norm)


def compute_all_derived_keys_for_efc_cm_and_return_hex_dict(pan_8_msb:bytes, efc_cm:str, ac_cr_key_ref:int, norm:str='TIS_decimal'):
    master_keys = tc_td_security_operations.get_master_keys_with_efc_cm_only_on_td(efc_cm)
    return dsrc_key_derivation.compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys, norm)

def compute_all_derived_keys_for_device_contract_ref_and_return_hex_dict(pan_8_msb:bytes, device_contract_ref:str, ac_cr_key_ref:int):
    master_keys = get_master_keys_with_device_contract_ref_on_td(device_contract_ref)
    efc_cm = device_contract_ref[0:12]
    return dsrc_key_derivation.compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)

def compute_all_derived_keys_for_device_model(pan_8_msb:bytes, device_model_name:str, ac_cr_key_ref:int):
    efc_cm_to_derived_keys = {}
    master_keys_by_efc_cm = tc_td_security_operations.get_master_keys_with_obu_model_only(device_model_name)
    for efc_cm, master_keys in master_keys_by_efc_cm.items():
        efc_cm_to_derived_keys[efc_cm] = dsrc_key_derivation.compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys)
    return efc_cm_to_derived_keys

def compute_all_derived_keys_by_device_contract_ref_in_td(pan_8_msb:bytes, ac_cr_key_ref:int, norm:str='TIS_decimal', td_name:str='TIS'):
    derived_keys_by_device_contract_ref = {}
    for device_contract_ref, master_keys in tc_td_security_operations.get_master_keys_by_obu_contract_from_td_name(td_name).items():
        efc_cm = device_contract_ref[0:12]

        derived_keys_hex_dict = dsrc_key_derivation.compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys, norm)
        derived_keys_by_device_contract_ref[device_contract_ref] = derived_keys_hex_dict
    return derived_keys_by_device_contract_ref

def compute_all_derived_keys_by_device_contract_ref_in_curr_td(pan_8_msb:bytes, ac_cr_key_ref:int, norm:str='TIS_decimal'):
    derived_keys_by_device_contract_ref = {}
    curr_td = tc_manage_toll_domains.current_toll_domain_name
    for device_contract_ref, master_keys in tc_td_security_operations.get_master_keys_by_obu_contract_from_td_name(curr_td).items():
        efc_cm = device_contract_ref[0:12]

        derived_keys_hex_dict = dsrc_key_derivation.compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys, norm)
        derived_keys_by_device_contract_ref[device_contract_ref] = derived_keys_hex_dict
    return derived_keys_by_device_contract_ref

def compute_all_derived_keys_by_keyset_name(pan_8_msb:bytes, efc_cm:str, ac_cr_key_ref:int, norm:str='TIS_decimal'):
    derived_keys_by_keyset_name = {}
    all_master_keysets = tc_manage_toll_domains.get_all_master_keysets()

    for keyset_name, master_keys_hex_dict in all_master_keysets:
        derived_keys_hex_dict = dsrc_key_derivation.compute_all_derived_keys_and_return_hex_dict(pan_8_msb, efc_cm, ac_cr_key_ref, master_keys_hex_dict, norm)
        derived_keys_by_keyset_name[keyset_name] = derived_keys_hex_dict
    return derived_keys_by_keyset_name

def decipher_auth_key_with_efc_cm_and_auk_ref(auth_key: str, efc_cm: str, auk_ref: int) -> bytes:
    mauk = tc_td_security_operations.get_master_keys_with_efc_cm_only_on_td(efc_cm)[str(auk_ref)]
    return dsrc_key_derivation.decipher_auth_key_with_mauk_value(auth_key, mauk)
