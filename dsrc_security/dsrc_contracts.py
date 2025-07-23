from dsrc_security import dsrc_mk_by_device_and_td_loader
import logging

class NoValidObeEfcmFoundInVst(Exception):
    pass

dsrc_contracts_logger = logging.getLogger(__name__)
# Remember to set the current_toll_domain_name global variable in the dsrc_mk_by_device_and_td_loader module!!!
def is_device_info_valid(efc_cm: str|int|bytes, manufacturer_id:str|int|bytes, equipment_class:str|int|bytes) -> bool:
    try:
        master_keys = dsrc_mk_by_device_and_td_loader.get_master_keys_with_device_info(efc_cm, manufacturer_id, equipment_class)
        # MasterKeys were found!
        return True
    except dsrc_mk_by_device_and_td_loader.TollDomainMasterKeysNotFoundException:
        return False

def get_eid_in_vst_with_valid_contract(vst_value: dict = None) -> int:
    """Get EID in VST with a valid EFC-CM for the current Toll Domain."""
    available_applications_list = vst_value['applications']
    for application_data in available_applications_list:
        app_parameter_type, app_parameter_value = application_data['parameter']
        efc_cm_bytes = app_parameter_value[0:8]
        dsrc_contracts_logger.debug(f'EFC-CM: 0x{efc_cm_bytes.hex().upper()}')

        obe_config = vst_value['obeConfiguration']
        equipment_class = obe_config['equipmentClass']
        manufacturer_id = obe_config['manufacturerID']

        
        if is_device_info_valid(efc_cm_bytes, manufacturer_id, equipment_class):
            return application_data['eid']
    dsrc_contracts_logger.error('Invalid or Unknown EFC-CM!!')
    raise NoValidObeEfcmFoundInVst(f'No valid EFC-CM (contract) found for the OBE with VST: {vst_value}')