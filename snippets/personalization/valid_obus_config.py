import json
from dsrc_security import dsrc_mk_by_device_and_td_loader

def generate_valid_obu_models_by_td_config():
    valid_obu_models_by_td = {}
    for toll_domain_name, mk_by_obu_contract_ref in dsrc_mk_by_device_and_td_loader.master_keys_by_toll_domain.items():
        for obu_contract_ref in mk_by_obu_contract_ref.keys():
            for device_model_name, obu_eq_ref_list in dsrc_mk_by_device_and_td_loader.equipment_refs_by_device_names.items():
                for obu_eq_ref in obu_eq_ref_list:
                    if obu_eq_ref == obu_contract_ref[12:20]:
                        valid_models = valid_obu_models_by_td.get(toll_domain_name, [])
                        valid_models.append(obu_eq_ref)
                        valid_obu_models_by_td[toll_domain_name] = valid_models

    with open('local_file_storage/valid_obu_models_by_td.json', 'w') as json_file:
        json.dump(valid_obu_models_by_td, json_file, indent=2)

def generate_valid_obu_models_from_efc_contracts_config():
    valid_obu_models_by_td = {}
    for toll_domain_name, mk_by_obu_contract_ref in dsrc_mk_by_device_and_td_loader.master_keys_by_toll_domain.items():
        valid_obu_models_by_td[toll_domain_name] = list(map(lambda obu_contract_ref: obu_contract_ref[12:20], mk_by_obu_contract_ref.keys()))

    with open('local_file_storage/valid_obu_models_by_td.json', 'w') as json_file:
        json.dump(valid_obu_models_by_td, json_file, indent=2)

generate_valid_obu_models_from_efc_contracts_config()