from dsrc_security import dsrc_td_security_operations
import logging

class NoValidObeEfcmFoundInVst(Exception):
    pass

dsrc_contracts_logger = logging.getLogger(__name__)
# Remember to set the current_toll_domain_name global variable in the dsrc_td_security_operations module!!!
def is_device_info_valid_in_current_td(efc_cm: str|int|bytes, manufacturer_id:str|int|bytes, equipment_class:str|int|bytes) -> bool:
    try:
        master_keys = dsrc_td_security_operations.get_master_keys_with_device_info_in_current_td(efc_cm, manufacturer_id, equipment_class)
        # MasterKeys were found!
        return True
    except dsrc_td_security_operations.TollDomainMasterKeysNotFoundException:
        return False

def get_eid_in_vst_with_valid_contract_in_current_td(vst_value: dict = None) -> int:
    """Get EID in VST with a valid EFC-CM for the current Toll Domain."""
    available_applications_list = vst_value['applications']
    for application_data in available_applications_list:
        app_parameter_type, app_parameter_value = application_data['parameter']
        efc_cm_bytes = app_parameter_value[0:6]
        dsrc_contracts_logger.debug(f'EFC-CM: 0x{efc_cm_bytes.hex().upper()}')

        obe_config = vst_value['obeConfiguration']
        equipment_class = obe_config['equipmentClass']
        manufacturer_id = obe_config['manufacturerID']

        
        if is_device_info_valid_in_current_td(efc_cm_bytes, manufacturer_id, equipment_class):
            return application_data['eid']
    dsrc_contracts_logger.error(f'No valid EFC-CM (contract) found for the OBE with VST apps: {available_applications_list}')
    raise NoValidObeEfcmFoundInVst(f'No valid EFC-CM (contract) found for the OBE with VST: {available_applications_list}')