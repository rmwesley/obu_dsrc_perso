import json
import pathlib

# Loading the Master Keys from a JSON into a Python dict
# This dict maps an EFC-CM in hex format to a MasterKeySet also in hex format

# We use absolute paths to the root package
package_root_dir = pathlib.Path(__file__).parent.parent
tc_conf_json_path = package_root_dir / 'settings/toll_domain_security_config.json'
with tc_conf_json_path.open('r') as json_file:
    toll_domain_config_json = json.load(json_file)
    toll_domains_conf_path = package_root_dir / toll_domain_config_json['toll_domains_conf_path']
    del toll_domain_config_json

with open(toll_domains_conf_path, 'r') as json_file:
    toll_domains_conf = json.load(json_file)

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

def load_toll_domains_config():
    global toll_domains_conf
    # Setting up EFC-CM + Equipment Class to Master Key mapping, by Toll Domain!
    master_keys_by_toll_domain = {}

    for toll_domain_name, contracts_by_manufacturer in toll_domains_conf.items():
        # Assembling masterkeys for a Toll Domain!!
        master_keys_by_toll_domain[toll_domain_name] = {}
        for manufacturer_id_hex, contract_by_obu_eq_class in contracts_by_manufacturer.items():
            for equipment_class_hex, contract_data in contract_by_obu_eq_class.items():
                for efc_cm, td_conf in contract_data.items():
                    device_contract_ref = assemble_device_contract_ref_hex_str(efc_cm, manufacturer_id_hex, equipment_class_hex)

    return master_keys_by_toll_domain