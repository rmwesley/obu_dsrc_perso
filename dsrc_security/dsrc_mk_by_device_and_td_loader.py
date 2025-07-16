import os
import json

import logging

key_derivation_logger = logging.getLogger(__name__)

# Loading the Master Keys from a JSON into a Python dict
# This dict maps an EFC-CM in hex format to a MasterKeySet also in hex format

with open(f'settings/toll_domain_config.json') as json_file:
    toll_domain_config_json = json.load(json_file)
    default_toll_domain_name = toll_domain_config_json['default_toll_domain_name']
    td_conf_by_td_name = toll_domain_config_json['td_conf_by_td_name']
    efc_sec_conf_path = toll_domain_config_json['efc_sec_conf_path']

class TollDomainMasterKeysNotFoundException(Exception):
    pass

def assemble_device_contract_ref_hex_str(efc_cm: bytes|int|str, manufacturer_id:bytes|int|str, equipment_class:bytes|int|str):
    if type(manufacturer_id) is int:
        manufacturer_id = f'{manufacturer_id:04X}'
    if type(equipment_class) is int:
        equipment_class = f'{equipment_class:04X}'
    if type(efc_cm) is int:
        efc_cm = f'{efc_cm:12X}'

    if type(manufacturer_id) is bytes:
        manufacturer_id = manufacturer_id.hex().upper()
    if type(equipment_class) is bytes:
        equipment_class = equipment_class.hex().upper()
    if type(efc_cm) is bytes:
        efc_cm = efc_cm.hex().upper()

    # Pad to the left if too short, cut down if too long
    if type(manufacturer_id) is str:
        manufacturer_id = manufacturer_id.zfill(4)[-4:].upper()
    if type(equipment_class) is str:
        equipment_class = equipment_class.zfill(4)[-4:].upper()
    if type(efc_cm) is str:
        efc_cm = efc_cm.zfill(12)[-12:].upper()

    device_contract_hex_ref = f'{efc_cm}{manufacturer_id}{equipment_class}'
    return device_contract_hex_ref

def disassemble_device_contract_ref_hex_str(device_contract_ref: str) -> tuple[str, str, str]:
    efc_cm_hex = device_contract_ref[0:12]
    manufacturer_id_hex = device_contract_ref[12:16]
    equipment_class_hex = device_contract_ref[16:20]

    return (efc_cm_hex, manufacturer_id_hex, equipment_class_hex)

def get_efc_cm_from_device_contract_ref(device_contract_ref: str) -> str:
    return device_contract_ref[0:12]

# Device name to Manufacturer Id + Equipment Class mapping (in hex!!)
equipment_refs_by_device_names = {}
with open(f'settings/obu_product_names.json', 'r') as json_file:
    obu_models_data = json.load(json_file)
    equipment_refs_by_device_names = {}
    for manufacturer_id, manufacturer_data in obu_models_data['obe_name_by_device_model_ref'].items():
        for equipment_class, device_model_name in manufacturer_data['obu_names'].items():
            equipment_refs = equipment_refs_by_device_names.get(device_model_name, [])
            device_model_ref = manufacturer_id + equipment_class

            equipment_refs.append(device_model_ref)
            equipment_refs_by_device_names[device_model_name] = equipment_refs
    # print(equipment_refs_by_device_names)

def load_master_keys_by_toll_domain():
    global master_keys_by_toll_domain
    global master_keysets
    # Setting up EFC-CM + Equipment Class to Master Key mapping, by Toll Domain!
    master_keys_by_toll_domain = {}
    with open(efc_sec_conf_path) as json_file:
        efc_security_config = json.load(json_file)
        master_keysets = efc_security_config['keysets']

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

                    master_keys_by_toll_domain[toll_domain_name][device_contract_ref] = master_keysets[keyset_name]

        # toll_domain_security_profiles = efc_security_config['toll_domain_security_profiles']
        del efc_security_config
    return master_keys_by_toll_domain

class TollDomainSecurityProfileInvalidException(Exception):
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
    global master_keys_by_toll_domain

    # Check if Toll Domain has Master Keys properly configured
    if toll_domain_name in master_keys_by_toll_domain:
        current_toll_domain_name = toll_domain_name        
        master_keys_by_device_contract_ref = master_keys_by_toll_domain[current_toll_domain_name]
    else:
        raise TollDomainMasterKeysNotFoundException('NO MASTERKEYS FOUND FOR GIVEN TOLL DOMAIN')

def get_all_master_keysets():
    global master_keysets
    return master_keysets

def get_master_keys_with_device_info(efc_cm: bytes|int|str, manufacturer_id:bytes|int|str, equipment_class:bytes|int|str):
    """Get master keys through device (OBE) model data and EFC contract data
    All of these should be present in the OBE's VST!!!"""
    global master_keys_by_device_contract_ref
    device_contract_ref = assemble_device_contract_ref_hex_str(efc_cm, manufacturer_id, equipment_class)
    try:
        return master_keys_by_device_contract_ref[device_contract_ref]
        # get_master_keys_through_device_contract_data(efc_cm_hex_str, manufacturer_id_hex_str, equipment_class_hex_str)
    except KeyError:
        key_derivation_logger.critical(f'If you are communicating with a device, check the EquipmentObuId ({equipment_class}) and ManufacturerId ({manufacturer_id}) values that the device sent in its VST', stack_info=True)

        if toll_domain_config_json['try_looking_up_master_keys_for_other_obes_with_same_efc_cm']:
            # Trying to get masterkeys through EFC-CM only by looking up all devices!
            # Be careful if there are repeated EFC-CMs for different device models!!
            return get_master_keys_with_efc_cm_only(efc_cm)
        raise TollDomainMasterKeysNotFoundException(f'MasterKeys not found for device contract {device_contract_ref}!!!')

def get_master_keys_with_device_contract_ref(device_contract_ref: str):
    efc_cm_hex, manufacturer_id_hex, equipment_class_hex = disassemble_device_contract_ref_hex_str(device_contract_ref)
    return get_master_keys_with_device_info(efc_cm_hex, manufacturer_id_hex, equipment_class_hex)

def get_master_keys_with_efc_cm_only(efc_cm_hex_str: str):
    """No device model provided, only an EFC-CM for the current Toll Domain!!"""
    global master_keys_by_device_contract_ref
    key_derivation_logger.info('Looking up for a EFC-CM match in any MasterKey bundle for all configured device types/models...')

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
        device_equipment_ref_list = equipment_refs_by_device_names[device_model_name]
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

load_master_keys_by_toll_domain()
set_toll_domain(toll_domain_name=default_toll_domain_name)