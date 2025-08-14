import json

with open('../security_info/toll_charging/efc_contracts_and_keysets_by_toll_domain_and_obu_models_v1.0.1.json', 'r') as json_file:
    efc_contracts_and_keysets_by_toll_domain_and_obu_models = json.load(json_file)
    keyset_name_by_toll_domain_obu_model_and_efc_cm = efc_contracts_and_keysets_by_toll_domain_and_obu_models
    for td, obu_model in keyset_name_by_toll_domain_obu_model_and_efc_cm.items():
        for man_id, obu_info in obu_model.items():
            for eq_class, contract_info in obu_info.items():
                obu_info[eq_class] = {
                    contract_info['EFC-CM'] : contract_info['keyset_name']
                }

with open('../security_info/toll_charging/keyset_name_by_toll_domain_obu_model_and_efc_cm_v1.0.0.json', 'w') as json_file:
     json.dump(efc_contracts_and_keysets_by_toll_domain_and_obu_models, json_file, indent=2)