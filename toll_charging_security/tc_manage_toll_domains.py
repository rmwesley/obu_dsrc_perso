import json
import pathlib
import logging

from toll_charging_security import tc_default_td_value_handler, tc_td_security_operations

from obu_dsrc_security.dsrc_security import dsrc_mk_by_device_and_td_loader

td_security_logger = logging.getLogger(__name__)
td_security_logger.setLevel('INFO')

default_toll_domain_name = tc_default_td_value_handler.get_default_toll_domain_name()

# Default TD config!!
# Set at startup
package_root_dir = pathlib.Path(__file__).parent.parent
# tc_conf_json_path = package_root_dir / 'settings/toll_charging_config.json'
# with tc_conf_json_path.open() as json_file:
#     default_tc_conf_json = json.load(json_file)

toll_domain_management_conf_path = package_root_dir / f'settings/td_transaction_config.json'
with toll_domain_management_conf_path.open() as json_file:
    toll_domain_security_config_json = json.load(json_file)
    td_sec_conf_by_td_name = toll_domain_security_config_json['td_conf_by_td_name']

# WRAPPER ON TC TD SecOps with a TD name global variable set!
# Helps with the managing the currently set Toll Domain...
def set_td_security_config(td_config:dict):
    global current_td_config
    current_td_config = td_config

def get_master_keys_for_obu_on_td(efc_cm, manufacturer_id, equipment_class, td_name):
    global current_td_config
    if 'try_looking_up_master_keys_for_other_obes_with_same_efc_cm' in current_td_config:
        if current_td_config['try_looking_up_master_keys_for_other_obes_with_same_efc_cm']:
            try:
                return tc_td_security_operations.get_master_keys_for_obu_on_td(efc_cm, manufacturer_id, equipment_class, td_name)
            except tc_td_security_operations.ObuMasterKeysNotFoundException:
                # Trying to get masterkeys through EFC-CM only by looking up all kwnown OBU contracts!
                # Be careful if there are repeated EFC-CMs for different device models!!
                return tc_td_security_operations.get_master_keys_with_efc_cm_only_on_td(efc_cm, td_name)
    return tc_td_security_operations.get_master_keys_for_obu_on_td(efc_cm, manufacturer_id, equipment_class, td_name)

class TollDomainSecurityProfileInvalidException(Exception):
    pass

def get_current_security_profile():
    current_security_profile = current_td_config['security_profile']

    VALID_SECURITY_NORMS = ['TIS_decimal', 'EN15509']
    if not any([security_type in current_security_profile for security_type in VALID_SECURITY_NORMS]):
        td_security_logger.error(f'Invalid security profile: {current_security_profile}.')
        raise TollDomainSecurityProfileInvalidException(f'The only valid security norms are {VALID_SECURITY_NORMS}, with levels 0 and 1.')
    return current_security_profile

def get_current_security_norm() -> str:
    global current_td_config
    if 'EN15509' in current_td_config['security_profile']:
        return 'EN15509'
    elif 'TIS_decimal' in current_td_config['security_profile']:
        return 'TIS_decimal'

def td_is_en15509_level_1() -> bool:
    current_security_profile = current_td_config['security_profile']
    return 'level_1' in current_security_profile

def get_all_master_keysets():
    return dsrc_mk_by_device_and_td_loader.master_keysets

class TollDomainConfigUndefined(ValueError):
    pass

def set_toll_domain(toll_domain_name:str):
    global current_toll_domain_name

    if 'current_toll_domain_name' in globals() and current_toll_domain_name == toll_domain_name:
        td_security_logger.info(f"Toll Domain is already set to ({toll_domain_name}).")
        return

    td_security_logger.info(f"Switching Toll Domain to ({toll_domain_name})...")
    tc_td_security_operations.get_master_keys_by_obu_contract_from_td_name(toll_domain_name)

    if toll_domain_name not in td_sec_conf_by_td_name:
        # Better than a KeyError being raised!
        raise TollDomainConfigUndefined('Please setup the Toll Domain config in toll_domain_security_config.json!')
    set_td_security_config(td_sec_conf_by_td_name[toll_domain_name])
    current_toll_domain_name = toll_domain_name

def update_default_toll_domain(toll_domain_name:str):
    global default_toll_domain_name

    if default_toll_domain_name == toll_domain_name:
        td_security_logger.debug(f"Default Toll Domain is already ({toll_domain_name}).")
        return

    default_toll_domain_name = toll_domain_name
    td_security_logger.info(f"Updated Default Toll Domain to: ({toll_domain_name})")

def reset_toll_domain():
    global default_toll_domain_name
    return set_toll_domain(default_toll_domain_name)

def get_current_toll_domain():
    global current_toll_domain_name
    return current_toll_domain_name

# Set default Toll Domain!!
set_toll_domain(toll_domain_name=default_toll_domain_name)