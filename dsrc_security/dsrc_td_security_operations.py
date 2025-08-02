import os
import json

import logging

from dsrc_security import dsrc_mk_by_device_and_td_loader

td_security_logger = logging.getLogger(__name__)

with open(f'settings/toll_domain_config.json') as json_file:
    toll_domain_config_json = json.load(json_file)
    default_toll_domain_name = toll_domain_config_json['default_toll_domain_name']
    td_conf_by_td_name = toll_domain_config_json['td_conf_by_td_name']

class TollDomainSecurityProfileInvalidException(Exception):
    pass

class TollDomainMasterKeysNotFoundException(Exception):
    pass

def get_current_security_profile():
    global current_toll_domain_name
    current_security_profile = td_conf_by_td_name[current_toll_domain_name]['security_profile']
    # if current_security_profile not in ['TIS_decimal', 'EN15509']:
    #     raise TollDomainSecurityProfileInvalidException('The only valid security profile options are (TIS_decimal) or (EN15509)')
    return current_security_profile

current_toll_domain_name = 'TIS'
master_keys_by_device_contract_ref = {}
def set_toll_domain(toll_domain_name:str):
    global current_toll_domain_name
    global master_keys_by_device_contract_ref

    # print(f'Setting TD to {toll_domain_name}')
    if current_toll_domain_name == toll_domain_name:
        td_security_logger.debug(f"Toll Domain is already set to: {toll_domain_name}.")
        return

    td_security_logger.info(f"Switched Toll Domain to: {toll_domain_name}")
    # Check if Toll Domain has Master Keys properly configured
    if toll_domain_name in dsrc_mk_by_device_and_td_loader.master_keys_by_toll_domain:
        current_toll_domain_name = toll_domain_name        
        master_keys_by_device_contract_ref = dsrc_mk_by_device_and_td_loader.master_keys_by_toll_domain[current_toll_domain_name]
    else:
        raise TollDomainMasterKeysNotFoundException(f'NO MASTERKEYS FOUND FOR TOLL DOMAIN ({toll_domain_name})')

def get_current_toll_domain():
    global current_toll_domain_name
    return current_toll_domain_name

def get_all_master_keysets():
    return dsrc_mk_by_device_and_td_loader.master_keysets

def get_master_keys_with_device_info(efc_cm: bytes|int|str, manufacturer_id:bytes|int|str, equipment_class:bytes|int|str):
    """Get master keys through device (OBE) model data and EFC contract data
    All of these should be present in the OBE's VST!!!"""
    global master_keys_by_device_contract_ref
    # print(type(efc_cm))
    device_contract_ref = dsrc_mk_by_device_and_td_loader.assemble_device_contract_ref_hex_str(efc_cm, manufacturer_id, equipment_class)
    # print(master_keys_by_device_contract_ref)
    try:
        return master_keys_by_device_contract_ref[device_contract_ref]
        # get_master_keys_through_device_contract_data(efc_cm_hex_str, manufacturer_id_hex_str, equipment_class_hex_str)
    except KeyError:
        # key_derivation_logger.critical(f'If you are communicating with a device, check the EquipmentObuId ({equipment_class}) and ManufacturerId ({manufacturer_id}) values that the device sent in its VST', stack_info=True)

        if toll_domain_config_json['try_looking_up_master_keys_for_other_obes_with_same_efc_cm']:
            # Trying to get masterkeys through EFC-CM only by looking up all devices!
            # Be careful if there are repeated EFC-CMs for different device models!!
            return get_master_keys_with_efc_cm_only(efc_cm)
        raise TollDomainMasterKeysNotFoundException(f'MasterKeys not found for device contract {device_contract_ref}!!!')

def get_master_keys_with_device_contract_ref(device_contract_ref: str):
    efc_cm_hex, manufacturer_id_hex, equipment_class_hex = dsrc_mk_by_device_and_td_loader.disassemble_device_contract_ref_hex_str(device_contract_ref)
    return get_master_keys_with_device_info(efc_cm_hex, manufacturer_id_hex, equipment_class_hex)

def get_master_keys_with_efc_cm_only(efc_cm_hex_str: str):
    """No device model provided, only an EFC-CM for the current Toll Domain!!"""
    global master_keys_by_device_contract_ref
    td_security_logger.info('Looking up for a EFC-CM match in any MasterKey bundle for all configured device types/models...')

    efc_cm_hex_str = efc_cm_hex_str.upper()
    for device_contract_ref, master_keys in master_keys_by_device_contract_ref.items():
        if device_contract_ref[0:12] == efc_cm_hex_str:
            return master_keys
    raise TollDomainMasterKeysNotFoundException(f'Master Keys not found for EFC-CM {efc_cm_hex_str}!!!')

def get_master_keys_with_device_model_only(device_model_name: str):
    """No EFC-CM provided, only a device model name for the current Toll Domain!!"""
    global master_keys_by_device_contract_ref
    master_keyset_names_by_efc_cm = {}
    try:
        device_equipment_ref_list = dsrc_mk_by_device_and_td_loader.equipment_refs_by_device_names[device_model_name]
    except KeyError:
        raise TollDomainMasterKeysNotFoundException(f'Master Keys not found for device model with name {device_model_name}!!!')
    for device_contract_ref, master_keys in master_keys_by_device_contract_ref.items():
        equipment_reference = device_contract_ref[12:20]

        # Found a keyset for the given device model in the current Toll Domain!!
        if equipment_reference in device_equipment_ref_list:
            efc_cm = device_contract_ref[0:12]
            master_keyset_names_by_efc_cm[efc_cm] = master_keys
    if not master_keyset_names_by_efc_cm:
        raise TollDomainMasterKeysNotFoundException(f'Master Keys not found for device model with name {device_model_name}!!!')
    return master_keyset_names_by_efc_cm

# Set defaults!!
set_toll_domain(toll_domain_name=default_toll_domain_name)