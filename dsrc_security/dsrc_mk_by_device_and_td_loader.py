import os
import json

import logging

# Loading the Master Keys from a JSON into a Python dict
# This dict maps an EFC-CM in hex format to a MasterKeySet also in hex format

with open(f'settings/toll_domain_config.json', 'r') as json_file:
    toll_domain_config_json = json.load(json_file)
    efc_contracts_conf_path = toll_domain_config_json['efc_contracts_conf_path']
    master_keys_conf_path = toll_domain_config_json['master_keysets_conf_path']
    del toll_domain_config_json

with open(efc_contracts_conf_path, 'r') as json_file:
    efc_contracts = json.load(json_file)

with open(master_keys_conf_path, 'r') as json_file:
    master_keys = json.load(json_file)

class InvalidDeviceContractRef(Exception):
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
        if len(efc_cm) != 12:
            raise InvalidDeviceContractRef(f'EFC-CM (0x{efc_cm}) is too long!')
        efc_cm = efc_cm.zfill(12)[-12:].upper()
        # print(efc_cm)

    device_contract_hex_ref = f'{efc_cm}{manufacturer_id}{equipment_class}'
    # print(f'device_contract_ref: {device_contract_ref}')
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
    global master_keys
    global efc_contracts
    # Setting up EFC-CM + Equipment Class to Master Key mapping, by Toll Domain!
    master_keys_by_toll_domain = {}

    for toll_domain_name, contracts_by_manufacturer in efc_contracts.items():
        # Assembling masterkeys for a Toll Domain!!
        master_keys_by_toll_domain[toll_domain_name] = {}
        for manufacturer_id_hex, contract_by_obu_eq_class in contracts_by_manufacturer.items():
            for equipment_class_hex, contract_data in contract_by_obu_eq_class.items():
                keyset_name = contract_data['keyset_name']
                efc_cm = contract_data['EFC-CM']

                # This dictionary makes it easier to find a keyset!!
                # The dictionary keys are a concatenation of the EFC-CM, Manufacturer Id and Equipment Class!!
                device_contract_ref = assemble_device_contract_ref_hex_str(efc_cm, manufacturer_id_hex, equipment_class_hex)

                master_keys_by_toll_domain[toll_domain_name][device_contract_ref] = master_keys[keyset_name]

    del efc_contracts
    del master_keys
    return master_keys_by_toll_domain

master_keys_by_toll_domain = load_master_keys_by_toll_domain()