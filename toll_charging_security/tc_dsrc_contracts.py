import logging

from . import tc_td_security_operations, tc_manage_toll_domains

class NoValidObeEfcmFoundInVst(Exception):
    pass

dsrc_contracts_logger = logging.getLogger(__name__)

def get_eid_in_vst_with_valid_contract_in_td(vst_value: dict, td_name: str) -> int:
    """Get EID in VST with a valid EFC-CM for a given Toll Domain."""
    available_applications_list = vst_value['applications']

    obe_config = vst_value['obeConfiguration']
    equipment_class = obe_config['equipmentClass']
    manufacturer_id = obe_config['manufacturerID']
    dsrc_contracts_logger.info(f'OBU equipment ref: 0x{manufacturer_id:04X}{equipment_class:04X}')

    obu_contract_ref_list = []
    for application_data in available_applications_list:
        app_parameter_type, app_parameter_value = application_data['parameter']
        efc_cm_bytes = app_parameter_value[0:6]

        efc_cm_hex = efc_cm_bytes.hex().upper()
        dsrc_contracts_logger.debug(f'EFC-CM: 0x{efc_cm_hex}')

        obu_contract_ref = f'{efc_cm_hex}{manufacturer_id:04X}{equipment_class:04X}'
        obu_contract_ref_list.append(obu_contract_ref)
        if tc_td_security_operations.check_if_obu_contract_is_known_on_td(efc_cm_bytes, manufacturer_id, equipment_class, td_name):
            return application_data['eid']
    dsrc_contracts_logger.error(f'No valid EFC-CM found in TD ({td_name}) for OBU Eq Refs: {obu_contract_ref_list}')
    raise NoValidObeEfcmFoundInVst(f'No valid EFC-CM found in TD ({td_name}) for OBU Eq Refs: {obu_contract_ref_list}')

def get_eid_in_vst_with_valid_contract_in_current_td(vst_value: dict) -> int:
    """Get EID in VST with a valid EFC-CM for the current Toll Domain."""
    # Remember to set the current_toll_domain_name global variable in the tc_td_security_operations module!!!
    current_td = tc_manage_toll_domains.get_current_toll_domain(vst_value)
    return get_eid_in_vst_with_valid_contract_in_td(vst_value, current_td)
