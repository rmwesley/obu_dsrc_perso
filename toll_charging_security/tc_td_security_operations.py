import logging

from obu_dsrc_security.dsrc_security import dsrc_mk_by_device_and_td_loader

td_security_logger = logging.getLogger(__name__)

class TollDomainMasterKeysNotFoundException(Exception):
    pass

def get_master_keys_by_obu_contract_from_td_name(toll_domain_name:str):
    # Check if Master Keys could properly be loaded for Toll Domain
    if toll_domain_name in dsrc_mk_by_device_and_td_loader.master_keys_by_toll_domain:
        master_keys_by_obu_contract = dsrc_mk_by_device_and_td_loader.master_keys_by_toll_domain[toll_domain_name]
        # print(master_keys_by_obu_contract)
        return master_keys_by_obu_contract
    else:
        raise TollDomainMasterKeysNotFoundException(f'NO MASTERKEYS FOUND FOR TOLL DOMAIN ({toll_domain_name})')

def get_known_obu_contract_refs_on_td(td_name:str="TIS"):
    """Get valid contracts keys on current TD"""
    master_keys_by_obu_contract_ref = get_master_keys_by_obu_contract_from_td_name(td_name)
    return master_keys_by_obu_contract_ref.keys()

def check_if_obu_contract_is_known_on_td(efc_cm: bytes|int|str, manufacturer_id:bytes|int|str, equipment_class:bytes|int|str, td_name:str="TIS"):
    obu_contract_ref = dsrc_mk_by_device_and_td_loader.assemble_device_contract_ref_hex_str(efc_cm, manufacturer_id, equipment_class)
    valid_contracts = get_known_obu_contract_refs_on_td(td_name)
    result = obu_contract_ref in valid_contracts
    if not result:
        td_security_logger.debug(f'OBU contract {obu_contract_ref} not valid in TD {td_name}! Valid contracts: {valid_contracts}')
    return result

class ObuMasterKeysNotFoundException(Exception):
    pass
class MasterKeysObjNotInitialized(Exception):
    pass

def get_master_keys_for_obu_on_td(efc_cm: bytes|int|str, manufacturer_id:bytes|int|str, equipment_class:bytes|int|str, td_name:str="TIS") -> dict[str, str]:
    """Get master keys through device (OBE) model data and EFC contract data
    All of these should be present in the OBE's VST!!!"""
    master_keys_by_obu_contract_ref = get_master_keys_by_obu_contract_from_td_name(td_name)
    # print(f'MKs on TD {td_name}: {master_keys_by_obu_contract_ref}')

    obu_contract_ref = dsrc_mk_by_device_and_td_loader.assemble_device_contract_ref_hex_str(efc_cm, manufacturer_id, equipment_class)
    if obu_contract_ref not in master_keys_by_obu_contract_ref:
        td_security_logger.error(f'MasterKeys not found for device contract {obu_contract_ref}!!!')
        raise ObuMasterKeysNotFoundException(f'MasterKeys not found for OBU with contract {obu_contract_ref} on TD {td_name}!!!')

    td_security_logger.info(f'MasterKeys found for device contract {obu_contract_ref}!!!')
    return master_keys_by_obu_contract_ref[obu_contract_ref]

def get_master_keys_with_obu_contract_ref_on_td(obu_contract_ref: str, td_name:str='TIS') -> dict[str, str]:
    efc_cm_hex, manufacturer_id_hex, equipment_class_hex = dsrc_mk_by_device_and_td_loader.disassemble_device_contract_ref_hex_str(obu_contract_ref)
    return get_master_keys_for_obu_on_td(efc_cm_hex, manufacturer_id_hex, equipment_class_hex, td_name)

class MasterKeysNotFoundForEfcCm(Exception):
    pass
def get_master_keys_with_efc_cm_only_on_td(efc_cm_hex_str: str, td_name:str='TIS'):
    """No device model provided, only an EFC-CM for the current Toll Domain!!"""
    master_keys_by_obu_contract_ref = get_master_keys_by_obu_contract_from_td_name(td_name)

    td_security_logger.info('Looking up for a EFC-CM match in any MasterKey bundle for all configured device types/models...')

    efc_cm_hex_str = efc_cm_hex_str.upper()
    for obu_contract_ref, master_keys in master_keys_by_obu_contract_ref.items():
        if obu_contract_ref[0:12] == efc_cm_hex_str:
            return master_keys
    td_security_logger.critical(f'Master Keys not found for EFC-CM {efc_cm_hex_str} on TD {td_name}!!!')
    raise MasterKeysNotFoundForEfcCm(f'Master Keys not found for EFC-CM {efc_cm_hex_str} on TD {td_name}!!!')

def get_master_keys_with_obu_model_only(obu_model_name: str, td_name:str='TIS'):
    """No EFC-CM provided, only a device model name for the current Toll Domain!!"""
    master_keys_by_obu_contract_ref = get_master_keys_by_obu_contract_from_td_name(td_name)

    master_keyset_names_by_efc_cm = {}
    try:
        device_equipment_ref_list = dsrc_mk_by_device_and_td_loader.equipment_refs_by_device_names[obu_model_name]
    except KeyError:
        raise ObuMasterKeysNotFoundException(f'Master Keys not found for device model with name {obu_model_name}!!!')
    for obu_contract_ref, master_keys in master_keys_by_obu_contract_ref.items():
        equipment_reference = obu_contract_ref[12:20]

        # Found a keyset for the given device model in the current Toll Domain!!
        if equipment_reference in device_equipment_ref_list:
            efc_cm = obu_contract_ref[0:12]
            master_keyset_names_by_efc_cm[efc_cm] = master_keys
    if not master_keyset_names_by_efc_cm:
        raise ObuMasterKeysNotFoundException(f'Master Keys not found for device model with name {obu_model_name}!!!')
    return master_keyset_names_by_efc_cm