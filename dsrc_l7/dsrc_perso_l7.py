import asyncio
import logging
import datetime

from dsrc_l7 import dsrc_l7_rse
from dsrc_security import dsrc_contracts, perso_security_operations
import custom_its_per_decoders

from ASN.compiled_DSRC_instances import AXXESv1_2

dsrc_l7_perso_logger = logging.getLogger(__name__)
dsrc_l7_perso_logger.setLevel(logging.DEBUG)

startup_date = datetime.datetime.now()
logs_date_prefix = startup_date.strftime('%y%m%d')

# SETTING UP LOGGER FILE HANDLER
file_handler = logging.FileHandler(f'logs/beacon_logs/{logs_date_prefix}_perso_l7.log')
file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)
dsrc_l7_perso_logger.addHandler(file_handler)

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
    dsrc_l7_perso_logger.info(f'OBU Equipment Reference: {obu_equipment_ref}')
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
    dsrc_l7_perso_logger.debug(f"SET.Response value: {dsrc_l7_rse.last_response_t_apdu_value[1]}")

    return response_t_apdu_value

# class AcCrKeyRefNotFound(Exception):
#     pass
# async def get_rnd_obe_and_ac_cr_key_ref_for_obe_from_cardme_app_in_vst(serial_number=None):
#     try:
#         # Works only if the OBU has an active CARDME application being presented in its VST!!
#         cardme_eid, efc_cm, ac_cr_key_ref, rnd_obe = custom_its_per_decoders.vst_decode_eid_efc_cm_rnd_obe_and_ac_cr_from_any_cardme_app_in_vst(dsrc_l7_rse.last_vst_value)
#         return ac_cr_key_ref, rnd_obe
#     except custom_its_per_decoders.NoCardmeAppPresentInVst:
#         dsrc_l7_perso_logger.warning('No CARDME apps were presented in VST!!')
#     if serial_number is not None:
#         # An OBU Serial Number was manually scanned and inputted to the script!!
#         # We can derive the AC_CR-KeyRef from the corresponding Equipment OBU ID!!
#         ac_cr_key_ref = compute_kapsch_ac_cr_key_ref_from_serial_number(serial_number)
#     else:
#         # Worst case scenario: No CARDME app in VST and no manually scanned Serial Number!
#         # Tryhard method: GET.request to Attribute 24 (equOBUId) on all available EIDs!!!
#         eq_obu_id = try_to_get_obu_id_from_any_eid_in_last_vst()
#         if eq_obu_id is None:
#             raise AcCrKeyRefNotFound("Please scan the OBU's serial number so we can determine its AC_CR-KeyRef! The OBU ID is not present in any EID...")
#         ac_cr_key_ref = compute_kapsch_ac_cr_key_ref_from_eq_obu_id(eq_obu_id)
#     # Good! Now we have the AC_CR-KeyRef! Onto the RndOBE value...
#     rnd_obe = await send_get_nonce_action_req_and_decode_rnd_obe_value(eid=0)
#     return ac_cr_key_ref, rnd_obe

async def get_ac_cr_key_ref_from_any_cardme_app(serial_number=None):
    try:
        # Works only if the OBU has an active CARDME application being presented in its VST!!
        cardme_eid, efc_cm, ac_cr_key_ref, rnd_obe = custom_its_per_decoders.vst_decode_eid_efc_cm_rnd_obe_and_ac_cr_from_any_cardme_app_in_vst(dsrc_l7_rse.last_vst_value)
    except custom_its_per_decoders.NoCardmeAppPresentInVst:
        dsrc_l7_perso_logger.warning('No CARDME apps were presented in VST!!')
    return ac_cr_key_ref

async def get_ac_cr_key_ref_from_any_cardme_app_and_rnd_obe_with_get_nonce(serial_number=None):
    try:
        # Works only if the OBU has an active CARDME application being presented in its VST!!
        cardme_eid, efc_cm, ac_cr_key_ref, rnd_obe = custom_its_per_decoders.vst_decode_eid_efc_cm_rnd_obe_and_ac_cr_from_any_cardme_app_in_vst(dsrc_l7_rse.last_vst_value)
    except custom_its_per_decoders.NoCardmeAppPresentInVst:
        dsrc_l7_perso_logger.warning('No CARDME apps were presented in VST!!')
    rnd_obe = await send_get_nonce_action_req_and_decode_rnd_obe_value(eid=0)
    return ac_cr_key_ref, rnd_obe

async def get_rnd_obe_and_ac_cr_key_ref_for_obe_element_or_another_cardme_elment_with_rnd_obe_set_to_0(eid:int) -> tuple[int, int]:
    try:
        # Works only if the OBU has an active CARDME application being presented in its VST!!
        cardme_eid, efc_cm, ac_cr_key_ref, rnd_obe = custom_its_per_decoders.vst_decode_eid_efc_cm_rnd_obe_and_ac_cr_from_any_cardme_app_in_vst(dsrc_l7_rse.last_vst_value)
        if cardme_eid != eid:
            # AC_CR-KeyRef is a global value, but not rnd_obe...
            rnd_obe = 0
    except (custom_its_per_decoders.VstAppNotCardme, custom_its_per_decoders.EidNotFound):
        dsrc_l7_perso_logger.warning(f'VST app with EID {eid} is not CARDME')
        ac_cr_key_ref = 0
        rnd_obe = 0
    return ac_cr_key_ref, rnd_obe

# Get RndOBE by sending a GET_NONCE.request to the OBE!!
async def send_get_nonce_action_req(eid):
    # ACTION.request with a GET_NONCE.request ActionType (6)!!
    action_param_get_nonce_req_value = None
    action_req_value = {
        'mode': True,
        'eid': eid,
        'actionType': 6,
    }
    dsrc_l7_perso_logger.debug(f"ACTION.Request value: {action_req_value}")

    t_apdu_with_action_request_value = ('actionRequest', action_req_value)
    await dsrc_l7_rse.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_action_request_value)

    dsrc_l7_perso_logger.debug(f"ACTION.response with GET_NONCE.Response value: {dsrc_l7_rse.last_response_t_apdu_value}")

    return dsrc_l7_rse.last_response_t_apdu_value

# Decode RndOBE from GET_NONCE.request!!
async def send_get_nonce_action_req_and_decode_rnd_obe_value(eid):
    t_apdu_val = await send_get_nonce_action_req(eid)
    rnd_obe_bytes = t_apdu_val[1]['responseParameter'][1]
    return int.from_bytes(rnd_obe_bytes)

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

async def try_to_get_obu_id_from_any_eid_in_last_vst():
    for vst_app_data in dsrc_l7_rse.last_vst_value['applications']:
        eid = vst_app_data['eid']
        eq_obu_id = await send_request_to_get_eq_obu_id(eid)
        if eq_obu_id is not None:
            return eq_obu_id

class SetResponseError(Exception):
    pass

async def write_dsrc_data_to_kapsch_efc_element_with_kapsch_uset_ac_cr(eid:int, attribute_dict:dict, access_credentials:bytes):
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
                dsrc_l7_perso_logger.error(f'Access Denied: Cannot SET attribute for OBU! SET.response: {result}')
            await dsrc_l7_rse.send_close_transaction_echo(eid=eid, text='Error')
            raise SetResponseError(f'Error in set-response: {result['set-response']}')
            # break

    await dsrc_l7_rse.set_mmi(eid=eid)

async def kapsch_trp_4010_20b_pl_perso_single_eid(eid:int, attribute_dict, obu_model, uset_key_type=None):
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=[0, 1])
    obu_eq_ref = get_obu_model_from_vst_data(last_vst_value)
    perso_security_operations.check_obu_model(obu_eq_ref, obu_model)

    ac_cr_key_ref = await get_ac_cr_key_ref_from_any_cardme_app()
    rnd_obe = await send_get_nonce_action_req(eid)

    uset_access_credentials = perso_security_operations.compute_kapsch_uset_access_credentials_for_obu_model(obu_eq_ref, obu_model, ac_cr_key_ref, rnd_obe, uset_key_type)
    await write_dsrc_data_to_kapsch_efc_element_with_kapsch_uset_ac_cr(eid, attribute_dict, uset_access_credentials)

    await dsrc_l7_rse.send_close_transaction_echo(eid=eid)

async def perso_kapsch_element_with_uset(eid, obu_eq_ref, obu_model, attribute_dict, uset_key_type=None):
    ac_cr_key_ref = await get_ac_cr_key_ref_from_any_cardme_app()
    rnd_obe = await send_get_nonce_action_req(eid)

    perso_security_operations.check_obu_model(obu_eq_ref, obu_model)
    uset_access_credentials = perso_security_operations.compute_kapsch_uset_access_credentials_for_obu_model(obu_eq_ref, obu_model, ac_cr_key_ref, rnd_obe, uset_key_type)
    await write_dsrc_data_to_kapsch_efc_element_with_kapsch_uset_ac_cr(eid, attribute_dict, uset_access_credentials)

SLEEP_BETWEEN_EIDS_S = 0.3
async def kapsch_trp_4010_20b_pl_perso(obu_model, dsrc_memory_data, uset_key_type=None):
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=[0, 1])
    obu_eq_ref = get_obu_model_from_vst_data(last_vst_value)
    obu_id_hex = await try_to_get_obu_id_from_any_eid_in_last_vst()

    for eid, attribute_dict in dsrc_memory_data.items():
        if eid == 0:
            continue

        dsrc_l7_rse.get_parameter_for_eid(eid)
        perso_kapsch_element_with_uset(eid, obu_eq_ref, obu_model, attribute_dict, uset_key_type=uset_key_type)
        await asyncio.sleep(SLEEP_BETWEEN_EIDS_S)

    if 0 in dsrc_memory_data:
        # Setup System Element
        # Kapsch System Element uses AcK, not USET
        system_element_attrs = dsrc_memory_data[0]
        await perso_kapsch_element_with_uset(0, obu_eq_ref, obu_model, system_element_attrs, uset_key_type='SystemElementAcK')

    await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)

    return obu_id_hex

async def kapsch_element_switch_uset_keys(obu_model, obu_equipment_ref, ac_cr_key_ref, vst_value, curr_uset_key_type=None, new_uset_key_type=None):
    vst_eid_list = [app['eid'] for app in vst_value['applications']]
    dsrc_l7_perso_logger.info(f'OBU contains EIDs: {vst_eid_list}')

    uset_element_attribute_dict_by_eid = perso_security_operations.get_new_uset_attribute_dict_by_eid_for_obu_model(obu_model, ac_cr_key_ref, new_uset_key_type)
    for eid, uset_key_storage_eid_and_attribute in uset_element_attribute_dict_by_eid.items():
        if eid not in vst_eid_list:
            raise Exception(f'EID {eid} not in OBU VST EID list: {vst_eid_list}, so OBU is probably not of model {obu_model}')
        uset_key_eid = uset_key_storage_eid_and_attribute['uset_key_eid']

        if uset_key_eid not in vst_eid_list:
            raise Exception(f'USET key storage EID {uset_key_eid} not in in OBU VST EID list: {vst_eid_list}, so OBU is probably not of model {obu_model}')

        new_uset_attr_dict = uset_key_storage_eid_and_attribute['attribute_dict']
        await perso_kapsch_element_with_uset(eid, obu_equipment_ref, obu_model, new_uset_attr_dict, uset_key_type=curr_uset_key_type)

async def kapsch_switch_uset_keys(obu_model, curr_uset_key_type=None, new_uset_key_type=None):
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=[1])

    ac_cr_key_ref, rnd_obe = await get_ac_cr_key_ref_from_any_cardme_app_and_rnd_obe_with_get_nonce()
    obu_equipment_ref = get_obu_model_from_vst_data(last_vst_value)
    obu_id_hex = await try_to_get_obu_id_from_any_eid_in_last_vst()

    await kapsch_element_switch_uset_keys(obu_model, obu_equipment_ref, ac_cr_key_ref, last_vst_value, curr_uset_key_type, new_uset_key_type)

    await dsrc_l7_rse.send_close_transaction_setmmi(eid=0)

    return obu_id_hex

async def kapsch_force_uset_key(obu_model, new_uset_key_type=None):
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=[1])
    obu_equipment_ref = get_obu_model_from_vst_data(last_vst_value)
    obu_id_hex = await try_to_get_obu_id_from_any_eid_in_last_vst()

    for application_data in last_vst_value['applications']:
        eid = application_data['eid']
        if eid == 0:
            # We do not update/switch the Access/USET key for Kapsch's SystemElement (EID 0)!
            continue
        for curr_uset_key_type in ['SystemElementAcK', 'Stock', 'Exploit']:
            await kapsch_element_switch_uset_keys(eid, obu_model, curr_uset_key_type, new_uset_key_type)

    await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)

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