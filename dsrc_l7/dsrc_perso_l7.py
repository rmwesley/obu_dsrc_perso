import logging
import typing

from dsrc_l7 import dsrc_l7_rse
from dsrc_security import dsrc_contracts, perso_security_operations

from ASN.compiled_DSRC_instances import AXXESv1_2

dsrc_l7_perso_logger = logging.getLogger(__name__)
dsrc_l7_perso_logger.setLevel(logging.DEBUG)

async def init_perso_app():
    await dsrc_l7_rse.init_bcm_and_set_transparent_mode()

class AbortedPersonalization(Exception):
    pass

def get_obu_model_from_vst_data(vst_value: dict = None) -> str:
    """Get OBU's Manufacturer ID and Equipment Class values in VST."""
    obe_config = vst_value['obeConfiguration']
    equipment_class = obe_config['equipmentClass']
    manufacturer_id = obe_config['manufacturerID']

    obu_equipment_ref = f'{manufacturer_id:04X}{equipment_class:04X}'
    dsrc_l7_perso_logger.error(f'OBU Equipment Reference: {obu_equipment_ref}')
    return obu_equipment_ref

async def send_set_request(eid, access_credentials, attrList, close_transaction=False):
    # Get.Request is filled with 1 bit valued at 0
    set_req_value = {
        'eid': eid,
        'accessCredentials': access_credentials,
        'attrList': attrList,
        'fill': (0, 1)
    }

    AXXESv1_2.EfcDsrcGeneric.Set_Request.set_val(set_req_value)
    dsrc_l7_perso_logger.debug(f"SET.Request value: {AXXESv1_2.EfcDsrcGeneric.Set_Request._val}")

    t_apdu_with_get_request_value = ('setRequest', set_req_value)
    response_t_apdu_value = await dsrc_l7_rse.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_get_request_value, close_transaction=close_transaction)

    dsrc_l7_perso_logger.debug(f"SET.Response value: {AXXESv1_2.EfcDsrcGeneric.T_APDUs._val[1]}")

    return response_t_apdu_value

async def send_request_to_get_eq_obu_id(eid:int):
    if eid == 0:
        return
    response_t_apdu_jval = await dsrc_l7_rse.send_get_request(eid, attrIdList=[24]) #equOBUId
    get_resp_jval = response_t_apdu_jval['getResponse']

    # if get_resp_jval['ret'] != 0:
    #     raise Exception(f'GET.response Return Status: {get_resp_jval['ret']}')
    for attribute_data in get_resp_jval['attributelist']:
        if attribute_data['attributeId'] == 24:
            return attribute_data['attributeValue']['equOBUId'].upper()

class ObuSetAccessDenied(Exception):
    pass

async def write_dsrc_data_to_efc_element_with_uset_key(eid:int, attribute_dict, obu_equipment_ref):
    obu_id_hex = await send_request_to_get_eq_obu_id(eid)

    decoded_vst_param = dsrc_l7_rse.decode_vst_parameter_from_eid(eid=eid)
    rnd_obe = decoded_vst_param['RndOBE']
    ac_cr_key_ref = decoded_vst_param['AC_CR-KeyReference']

    uset_key = perso_security_operations.compute_uset_derived_key_for_obu_model(obu_equipment_ref, ac_cr_key_ref)

    access_credentials = perso_security_operations.compute_access_credentials_for_obu_model(obu_equipment_ref, ac_cr_key_ref, rnd_obe=rnd_obe)
    for attribute_id, attribute_value_hex in attribute_dict.items():
        attribute_value_uper_bytes = bytes.fromhex(attribute_value_hex)
        AXXESv1_2.EfcDsrcGeneric.EfcContainer.from_uper(attribute_value_uper_bytes)
        attribute_value = AXXESv1_2.EfcDsrcGeneric.EfcContainer._val
        attribute_list = [
            {
                'attributeId': attribute_id,
                'attributeValue': attribute_value
            }
        ]
        result = await dsrc_l7_rse.send_set_request(eid, access_credentials=access_credentials, attrList=attribute_list)
        if 'ret' in result['set-response']:
            if result['set-response']['ret'] == 1:
                dsrc_l7_perso_logger.error(f'Cannot set attribute for OBU with model {obu_equipment_ref} and ID 0x{obu_id_hex}! SET.response: {result}')
                raise ObuSetAccessDenied(f'Access Denied: Cannot set attribute for OBU with model {obu_equipment_ref} and ID 0x{obu_id_hex}!')

    await dsrc_l7_rse.set_mmi(eid=eid)
    return obu_id_hex

class WrongObuModel(Exception):
    pass

async def kapsch_trp_4010_20b_pl_perso_single_eid(eid:int, attribute_dict, expected_obu_eq_ref):
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=[0, 1])
    obu_equipment_ref = get_obu_model_from_vst_data(last_vst_value)

    if obu_equipment_ref != expected_obu_eq_ref:
        raise WrongObuModel(f'Bad OBU ManufacturerId and/or EquipmentClass values!\nExpected: {expected_obu_eq_ref}. Obtained: {obu_equipment_ref}')

    obu_id = await dsrc_l7_rse.send_get_request(eid, attrIdList=[24]) #equOBUId

    await write_dsrc_data_to_efc_element_with_uset_key(eid, attribute_dict, obu_equipment_ref)

    await dsrc_l7_rse.send_close_transaction_echo(eid=eid)

    return obu_id

async def kapsch_trp_4010_20b_pl_perso(dsrc_memory_data, expected_obu_eq_ref):
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=[0, 1])
    obu_equipment_ref = get_obu_model_from_vst_data(last_vst_value)

    if obu_equipment_ref != expected_obu_eq_ref:
        raise WrongObuModel(f'Bad OBU ManufacturerId and/or EquipmentClass values!\nExpected: {expected_obu_eq_ref}. Obtained: {obu_equipment_ref}')

    obu_ids = set()
    for eid, attribute_dict in dsrc_memory_data.items():
        obu_id_hex = await write_dsrc_data_to_efc_element_with_uset_key(eid, attribute_dict, obu_equipment_ref)

        obu_ids.add(obu_id_hex)
        if len(obu_ids) > 1:
            dsrc_l7_perso_logger.critical(f'OBU ID different between DSRC Elements during personalization!!! Current EID: {eid}. OBU IDs: {obu_ids}')

    await dsrc_l7_rse.send_close_transaction_echo(eid=eid)

    return obu_id_hex

async def validate_cardme_perso(force_eid=None):
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=[0, 1])

    if force_eid is not None:
        eid = force_eid
    else:
        result = perso_security_operations.get_expected_eid_for_obu_model(last_vst_value)
        eid = result['eid']

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=True, attrIdList=[24]) # Get equOBUId

    individualAttrId = [0, 32]
    for attrId in individualAttrId:
        response_t_apdu_val = await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=True, attrIdList=[attrId])
        print(response_t_apdu_val)

    await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)

async def validate_deperso(force_eid=None):
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=[0, 1])

    if force_eid is not None:
        eid = force_eid
    else:
        result = perso_security_operations.get_expected_eid_for_obu_model(last_vst_value)
        eid = result['eid']

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=True, attrIdList=[24]) # Get equOBUId

    individualAttrId = [0, 32]
    for attrId in individualAttrId:
        response_t_apdu_val = await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=True, attrIdList=[attrId])
        print(response_t_apdu_val)

    await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)

async def card_mepersonalization(force_eid=None, obu_eq_ref:str='00000000', attribute_hex_dict={}):
    pass
async def tis_vl_personalization(force_eid=None, obu_eq_ref:str='00000000'):
    """
    Used for TIS VL CIP CARDME/Liber-t perso.
    TIS: Télépéage Inter Sociétés
    CIP: Commission Interautoroutes Péage
    VL: Véhicule Léger
    """
    pass