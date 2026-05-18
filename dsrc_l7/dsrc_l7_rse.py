import sys

import pycrate_core.charpy

from ASN.compiled_DSRC_instances import AXXESv1_2
# from ASN.compiled_DSRC_instances import EFCv5
EFCv5 = AXXESv1_2
# from ASN.compiled_DSRC_instances import CCCv1
# from ASN.compiled_DSRC_instances import LACv2_1 as efc_asn_compilation

efc_asn_compilation = AXXESv1_2

from datetime import datetime
import json
import logging
import uuid
import pathlib
import asyncio

import typing

from bac_l7 import ops1955_bac_l7, pertel_bac_l7, tgbv_bac_l7

import custom_its_per_decoders
from toll_charging_security import tc_dsrc_auth, tc_manage_toll_domains

bcm_logger = logging.getLogger(__name__)
bcm_logger.setLevel(logging.WARNING)

# T-APDU logger only logs to file, no propagation!!
t_apdu_uper_logger = logging.getLogger('T_APDU_logger')
t_apdu_uper_logger.setLevel(logging.DEBUG)
t_apdu_uper_logger.propagate = False

local_transactions_storage_path_str = 'local_file_storage/transactions'
startup_date = datetime.now()
logs_date_prefix = startup_date.strftime('%y%m%d')

# SETTING UP LOGGER FILE HANDLER
file_handler = logging.FileHandler(f'logs/beacon_logs/{logs_date_prefix}_rse_dsrc_l7.log')
file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)
bcm_logger.addHandler(file_handler)

t_apdu_file_handler = logging.FileHandler(f'logs/beacon_logs/{logs_date_prefix}_rse_t_apdu_uper.log')
t_apdu_file_handler.setFormatter(file_formatter)
t_apdu_uper_logger.addHandler(t_apdu_file_handler)

# Setting globals
## Garbage unsafe temporary globals
keep_looping = False

## Beacon L7 necessary values
beacon_bac_l7_wrapper = None

## SKIP DSRC AUTH
SKIP_CONTRACT_DSRC_AUTH = False

def set_fragmentation_header():
    global frag_header
    # PDU cannot be 0 or 1
    pdu = 0x2
    # PDU is at most 4 bits
    pdu &= 0xF
    # The fragmentation header is 0b1xxxx001, where xxxx is the PDU
    frag_header = bytes([0x81 | (pdu << 3)]) # 0x91

# RSE <> OBE = Host <> Host BAC L2 <> Beacon BAC L2 <> Beacon DSRC L7 <> OBE DSRC L7
async def initialize_bcm(aid=20):
    """Initialize the beacon manager wrapper"""
    global beacon_manager_config
    global TApdu_container

    set_fragmentation_header()
    if aid == 1:
        TApdu_container = TApdu_container
    else:
        TApdu_container = efc_asn_compilation.EfcCcc.CccTApdus
    with open('settings/beacon_manager_config.json', 'r') as beacon_manager_config_file:
        beacon_manager_config = json.load(beacon_manager_config_file)

    default_beacon_name = beacon_manager_config["default_beacon_name"]
    await safe_set_beacon(chosen_beacon_name = default_beacon_name)
    bcm_logger.info("Initialized RSE DSRC L7!!")

    bcm_logger.debug("We now update/get the BeaconID (according to the beacon HW itself) before sending the BST")
    await check_and_update_beacon_state()

def reset_beacon():
    global beacon_bac_l7_wrapper

    bcm_logger.info('L7: Resetting beacon!!')
    beacon_bac_l7_wrapper.reset_beacon()

BeaconModes = typing.Literal['Stopped', 'Transparent', 'Maintenance']
async def change_trx_mode(mode_name:BeaconModes = 'Stopped'):
    global beacon_manager_config
    global current_beacon_name
    global beacon_bac_l7_wrapper

    if beacon_bac_l7_wrapper is None:
        bcm_logger.error("L7: Beacon not initialized/configured!!")
        return
    bcm_logger.info(f"Changing beacon mode to '{mode_name}'")

    tgbv_gea_bcm_operating_modes_enum_values = {
        'Stopped': 0x00,
        'Transparent': 0x01,
        'Maintenance': 0x03
    }
    if current_beacon_name == 'TGBV':
        mode_code = tgbv_gea_bcm_operating_modes_enum_values[mode_name]
        await beacon_bac_l7_wrapper.set_mode(mode_code=mode_code)

async def init_bcm_and_set_transparent_mode():
    global beacon_bac_l7_wrapper

    bcm_logger.debug("Instantiating/Initializing BeaconManager class...")
    await initialize_bcm()
    # SETTING BEACON TO TRANSPARENT MODE!!
    await change_trx_mode(mode_name='Transparent')

def shutdown_beacon():
    global beacon_bac_l7_wrapper
    if beacon_bac_l7_wrapper is None:
        bcm_logger.error("L7: Beacon not initialized/configured!!")
        return
    beacon_bac_l7_wrapper.shutdown()

def get_last_beacon_state():
    global beacon_bac_l7_wrapper
    if beacon_bac_l7_wrapper is None:
        bcm_logger.error("L7: Beacon not initialized/configured!!")
        return

    return beacon_bac_l7_wrapper.get_last_beacon_state_description()

def update_rnd_rse():
    global rnd_rse_bytes_value

    bcm_logger.debug(f"Updating DateAndTime/SessionTime value (to be used as RndRSE value)...")

    efc_asn_compilation.EfcDataDictionary.DateAndTime.set_val({
        'timeDate':{
            'year': datetime.utcnow().year,
            'month': datetime.utcnow().month,
            'day': datetime.utcnow().day,
        },
        'timeCompact':{
            'hours': datetime.utcnow().hour,
            'mins': datetime.utcnow().minute,
            'doubleSecs': datetime.utcnow().second // 2
        }
    })

    bcm_logger.debug(f"RndRSE or SessionTime value (of type DateAndTime) in ASN:\n{efc_asn_compilation.EfcDataDictionary.DateAndTime.to_asn1()}")
    rnd_rse_bytes_value = efc_asn_compilation.EfcDataDictionary.DateAndTime.to_uper()
    setattr(sys.modules[__name__], "rnd_rse_bytes_value", rnd_rse_bytes_value)

    bcm_logger.debug(f"RndRSE value (UPER hex): {rnd_rse_bytes_value.hex().upper()}")
    return rnd_rse_bytes_value

async def safe_set_beacon(chosen_beacon_name):
    """Set the chosen beacon"""
    global current_beacon_name
    global beacon_bac_l7_wrapper

    bcm_logger.info(f'Setting beacon to ({chosen_beacon_name})')
    if beacon_bac_l7_wrapper is not None:
        beacon_bac_l7_wrapper.close()

    if chosen_beacon_name == 'TGBV':
        beacon_bac_l7_wrapper = tgbv_bac_l7.TgbvBacL7()
        current_beacon_name = chosen_beacon_name

    if chosen_beacon_name == 'OPS1955':
        beacon_bac_l7_wrapper = ops1955_bac_l7.Ops1955BacL7()
        await beacon_bac_l7_wrapper.kapsch_set_config_from_settings()

        current_beacon_name = chosen_beacon_name

class BeaconManagerException(Exception):
    pass
class UnclosedTransactionException(Exception):
    pass
class TApduResponseException(Exception):
    pass
class EIDNotFoundException(Exception):
    pass
class AbortedInitPhase(Exception):
    pass
class NoBeaconInitialized(Exception):
    pass

# Start sending a BST
async def try_to_start_bst_emission_and_await_vst(fragmented_t_apdu_with_bst: bytes):
    # Finally start BST emission!!
    if 'bst_timeout_delay' in beacon_manager_config[current_beacon_name]['dsrc_l7_config']:
        bst_timeout_delay = beacon_manager_config[current_beacon_name]['dsrc_l7_config']['bst_timeout_delay']
        try:
            vst_awaitable = beacon_bac_l7_wrapper._pertel_start_bst_emission_and_await_vst(fragmented_t_apdu_with_bst)
            response = await asyncio.wait_for(vst_awaitable, timeout=bst_timeout_delay)
        except TimeoutError as exc:
            bcm_logger.error('BST response timeout!')
            await beacon_bac_l7_wrapper._pertel_stop_bst_emission()
            # raise exc
            raise AbortedInitPhase('BST response timeout!')
    else:
        response = await beacon_bac_l7_wrapper._pertel_start_bst_emission_and_await_vst(fragmented_t_apdu_with_bst)

    if response[1] == 2:
        bcm_logger.critical("A Transaction is unclosed!!")
        raise UnclosedTransactionException("A Transaction is unclosed!!")

    return response

async def start_bst_emission_and_await_vst(bst_value: dict):
    global TApdu_container
    global current_beacon_name

    efc_asn_compilation.EfcDsrcGeneric.BST.set_val(bst_value)
    bcm_logger.debug(f"BST in ASN:\n{efc_asn_compilation.EfcDsrcGeneric.BST.to_asn1()}")
    last_sent_bst = efc_asn_compilation.EfcDsrcGeneric.BST.to_uper()
    bcm_logger.debug(f"BST value (UPER hex): {last_sent_bst.hex().upper()}")

    initialization_request_value = ('initialisationRequest', bst_value)

    TApdu_container.set_val(initialization_request_value)
    # bcm_logger.debug(f"T_APDU containing BST in ASN:\n{TApdu_container.to_asn1()}")

    initialization_request_jval = TApdu_container._to_jval()
    last_sent_t_apdu_containing_bst = TApdu_container.to_uper()
    # bcm_logger.info(f"T_APDU containing BST (UPER hex): {TApdu_container.to_uper().hex().upper()}")
    t_apdu_uper_logger.debug(f'[TX] BST: 0x{last_sent_t_apdu_containing_bst.hex().upper()}')

    fragmented_t_apdu_with_bst = frag_header + last_sent_t_apdu_containing_bst
    bcm_logger.info(f"RSE is now emitting BST and awaiting VST from OBE...")

    try:
        response = await try_to_start_bst_emission_and_await_vst(fragmented_t_apdu_with_bst)
    except UnclosedTransactionException:
        bcm_logger.info('Closing unclosed leftover transaction...')
        await send_close_transaction_echo()
        await asyncio.sleep(0.1)

        response = await try_to_start_bst_emission_and_await_vst(fragmented_t_apdu_with_bst)

    bcm_logger.debug("We now get the lastest BeaconID just after starting the BST")

    await check_and_update_beacon_state()

    return initialization_request_jval

async def initialize_transaction(
        manufacturer_id=0x31,
        individual_id=0x111,
        mand_applications=[1, 20, 29],
        profile=0x00,
        profile_list=[0x00],
        non_mand_applications = [],
        timeout_delay:float=0
    ):
    """
    The initialization phase comprises 2 steps for the beacon:
    Start of a BST, and
    wait for a VST

    The initialization phase locks the transaction thread when a VST is received!
    When the transaction is closed (no longer in progress) the transaction lock is released.
    """
    global TApdu_container
    global last_response_t_apdu_value
    global last_response_t_apdu_json
    global last_vst_value

    global initialization_data

    await check_and_update_beacon_state()

    try:
        if beacon_bac_l7_wrapper._is_transaction_in_progress():
            bcm_logger.error("Do not try to initilize a transaction! One is already in progress!")
            # bcm_logger.debug("We lock the thread until the opened transaction is closed!")
            raise BeaconManagerException("Transaction already in progress!!")
    except:
        await send_close_transaction_echo()

    mand_applications = [{'aid': mandatory_aid} for mandatory_aid in mand_applications]
    bst_value = {
        'rsu': {
            'manufacturerid': manufacturer_id,
            'individualid': individual_id
            },
        'time': int(datetime.utcnow().timestamp()),
        'profile': profile,
        'mandApplications': mand_applications,
        'profileList': profile_list
        }

    # Finally start BST emission!!
    initialization_request_jval = await start_bst_emission_and_await_vst(bst_value=bst_value)

    bcm_logger.info("A VST was received!")
    fragmented_t_apdu_init_resp_datagram = beacon_bac_l7_wrapper.get_vst()
    # bcm_logger.debug(f"Fragmented T_APDU containing VST (UPER hex): {fragmented_t_apdu_init_resp_datagram.hex().upper()}")

    bcm_logger.debug("We now remove the fragmentation header and instantiate an T_APDU object from the response!")
    t_apdu_init_resp_datagram = bytes(fragmented_t_apdu_init_resp_datagram[1:])
    t_apdu_uper_logger.debug(f"[RX] VST: 0x{t_apdu_init_resp_datagram.hex().upper()}")

    bcm_logger.debug("We now instantiate a T_APDU object from the UPER response!")
    TApdu_container.from_uper(t_apdu_init_resp_datagram)
    bcm_logger.debug(f"T_APDU containing VST value: {TApdu_container._val}")
    bcm_logger.info(f"T_APDU containing VST in ASN:\n{TApdu_container.to_asn1()}")

    # bcm_logger.debug(f"T_APDU containing VST in JER:\n{TApdu_container.to_jer()}")
    last_response_t_apdu_json = TApdu_container._to_jval()
    last_response_t_apdu_value = TApdu_container._val

    # Storing VST in global var
    last_vst_value = last_response_t_apdu_value[1]

    create_transaction_data_file_from_init_phase_data(initialization_request_jval, last_response_t_apdu_json)

    return (bst_value, last_vst_value)

async def init_and_close_transaction(
        mand_applications=[],
        callback:typing.Callable[[dict, dict], typing.Coroutine[None, None, typing.Any]] = None,
        ):
    bst_value, vst_value = await initialize_transaction(mand_applications=mand_applications)
    try:
        result = await callback(bst_value, vst_value)
        bcm_logger.info('Transaction successful! Closing ...')
        await send_close_transaction_echo()
        return result
    except RuntimeError:
        bcm_logger.error('Error during transaction! Closing...')
        await send_close_transaction_echo()

class ObuResponseTimeout(Exception):
    pass
class CommandRefused(Exception):
    pass
async def send_req_t_apdu_and_obtain_resp_t_apdu(asn1_request_t_apdu_value, close_transaction=False) -> dict:
    global TApdu_container
    if close_transaction:
        bcm_logger.info(f"Closing Transaction!! Info: BAC L2 command for closing a transaction is 0x06.")

    bcm_logger.debug(f"Preparing request T-APDU to be sent...")
    TApdu_container.set_val(asn1_request_t_apdu_value)
    bcm_logger.info(f"Request T-APDU value: {TApdu_container._val}")

    # Needed to store transaction data as JSON!
    request_t_apdu_jval = TApdu_container._to_jval()

    request_t_apdu_uper = TApdu_container.to_uper()
    t_apdu_uper_logger.debug(f'[TX] Rq T-APDU: 0x{request_t_apdu_uper.hex().upper()}')

    fragmented_t_apdu_request = frag_header + request_t_apdu_uper

    # Sending command!!!
    bac_l2_response = (await beacon_bac_l7_wrapper
        ._pertel_send_dsrc_l7_command_with_close_transaction_option(
            fragmented_t_apdu_request,
            close_transaction
            )
    )
    bac_l2_error_code = bac_l2_response[1]
    if bac_l2_error_code != 0:
        # OBU Timeout (0x09 error code)
        if bac_l2_error_code == 0x09:
            raise ObuResponseTimeout('[BAC L2] Timeout OBE (0x09) received!!')
        if bac_l2_error_code == 0x01:
            raise CommandRefused(f'[BAC L2] Command Refused error (0x01)!!')
        if bac_l2_error_code == 0x03:
            raise Exception(f'[BAC L2] Command Refused due to beacon error (0x03)!!')

        else:
            bcm_logger.error(f'[BAC L2] Error code (0x{bac_l2_error_code:02X}) present in BAC L2 response!!')
            raise Exception(f'[BAC L2] Error code (0x{bac_l2_error_code:02X}) present in BAC L2 response!!')
    beacon_bac_l7_wrapper.last_t_apdu_response_datagram
    fragmented_t_apdu_with_response_bytes = beacon_bac_l7_wrapper.last_t_apdu_response_datagram
    bcm_logger.info(f"Fragmented T-APDU response obtained from beacon in hex (UPER hex): {fragmented_t_apdu_with_response_bytes.hex().upper()}")

    try:
        t_apdu_with_response_bytes = bytes(fragmented_t_apdu_with_response_bytes[1:])
        t_apdu_uper_logger.debug(f'[RX] Rs T-APDU: 0x{t_apdu_with_response_bytes.hex().upper()}')

        t_apdu_response_value = decode_t_apdu_response_uper(t_apdu_with_response_bytes)

        TApdu_container.set_val(t_apdu_response_value)
        response_t_apdu_jval = TApdu_container._to_jval()
    except UnclosedTransactionException:
        bcm_logger.error("Error when decoding T-APDU response!!")
        bcm_logger.info("Unclosed Transaction Exception: We simply send an ECHO.request to close the transaction...")

        eid = asn1_request_t_apdu_value[1]['eid']
        await send_close_transaction_echo(eid=eid)
        return

    # Storing transaction files T-APDUs locally as a JSON
    add_t_apdu_data_to_transaction_data(request_t_apdu_jval, response_t_apdu_jval)

    return response_t_apdu_jval

def create_transaction_data_file_from_init_phase_data(initialization_request_jval, initialization_response_jval):
    global current_transaction_id
    global transaction_data_filepath
    current_transaction_id = uuid.uuid1()

    transaction_data = {}
    transaction_data['_id'] = current_transaction_id.hex

    current_td = tc_manage_toll_domains.get_current_toll_domain()
    transaction_data['RseTollDomain'] = current_td
    # Equipment OBU ID, PAN and timestamps at the top!
    transaction_data['equOBUId'] = ""
    transaction_data['personalAccountNumber'] = ""
    transaction_data['obu_provided_invalid_attr_auth_stamp'] = False
    transaction_data['position_info'] = {}
    transaction_data['creation_time'] = ""
    transaction_data['last_update_timestamp'] = ""

    # initialization_data dict is a merge of the init request and response JSON values
    # initialization_data = initialization_request_jval | initialization_response_jval
    initialization_data = {}
    # Merging initialisationRequest json into initialization_data json dict
    initialization_data |= initialization_request_jval
    # Merging initialisationResponse json into initialization_data json dict
    initialization_data |= initialization_response_jval

    obeManufacturerID = initialization_data['initialisationResponse']['obeConfiguration']['manufacturerID']
    obeEquipmentClass = initialization_data['initialisationResponse']['obeConfiguration']['equipmentClass']
    # equOBUId = 0

    # Actual data at the bottom!
    transaction_data['data'] = {}
    transaction_data['data']['initialization_phase'] = initialization_data
    # Create an empty list for future data exchanges (ACTION/GET/SET requests...)
    transaction_data['data']['transaction_phase'] = []

    current_transaction_start_date = datetime.now()
    current_transaction_datetime_prefix = current_transaction_start_date.strftime("%Y%m%dT%H%M%S")

    transaction_data_filename = f"{current_transaction_datetime_prefix}_{current_td}_{obeManufacturerID:04X}_{obeEquipmentClass:04X}_00000000_{current_transaction_id}.json"
    transaction_data_filepath = pathlib.Path(f"local_file_storage/transactions/{transaction_data_filename}")

    with transaction_data_filepath.open('w') as json_file:
        transaction_data['creation_time'] = datetime.now().isoformat()
        json.dump(transaction_data, json_file, indent=2)
    return transaction_data

def rename_transaction_data_file(equOBUId_hex:str='00000000'):
    global transaction_data_filepath

    # Rename output file to include equOBUId!!
    original_obuidless_filename = transaction_data_filepath.name
    filename_parts_list = original_obuidless_filename.split('_')
    # Equipment OBU Id is in the third part of the string!
    filename_parts_list[4] = equOBUId_hex
    new_filename = '_'.join(filename_parts_list)
    new_filepath = transaction_data_filepath.with_name(new_filename)
    transaction_data_filepath = transaction_data_filepath.rename(new_filepath)

def search_json_action_transaction_data_for_attribute_data(action_request_jval, action_response_jval, attribute_id:int):
    if 'actionParameter' in action_request_jval:
        if 'gstrq' in action_request_jval['actionParameter']:
            if attribute_id in action_request_jval['actionParameter']['gstrq']['attributeIdList']:
                try:
                    for attribute_data in action_response_jval['responseParameter']['gstrs']['attributeList']:
                        if attribute_data['attributeId'] == attribute_id:
                            return attribute_data['attributeValue']
                except KeyError:
                    bcm_logger.error(f'ACTION response does not contain data for Attribute Id ({attribute_id})!!')
                    return {}
    return {}

def search_json_get_transaction_data_for_attribute_data(get_request_jval, get_response_jval, attribute_id:int):
    if attribute_id in get_request_jval['attrIdList']:
        try:
            for attribute_data in get_response_jval['attributelist']:
                if attribute_data['attributeId'] == attribute_id:
                    return attribute_data['attributeValue']
        except KeyError:
            bcm_logger.error(f'GET response does not contain data for Attribute Id ({attribute_id})!!')
            return {}
    return {}

def search_json_t_apdu_exchange_data_for_attribute_value(request_t_apdu_jval, response_t_apdu_jval, attribute_id:int):
    if 'actionRequest' in request_t_apdu_jval:
        action_req_jval = request_t_apdu_jval['actionRequest']
        action_resp_jval = response_t_apdu_jval['actionResponse']

        attribute_value = search_json_action_transaction_data_for_attribute_data(action_req_jval, action_resp_jval, attribute_id)
        return attribute_value

    if 'getRequest' in request_t_apdu_jval:
        get_req_jval = request_t_apdu_jval['getRequest']
        get_resp_jval = response_t_apdu_jval['getResponse']

        attribute_value = search_json_get_transaction_data_for_attribute_data(get_req_jval, get_resp_jval, attribute_id)
        return attribute_value
    return {}

def search_for_obu_id_value_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval):
    attribute_value = search_json_t_apdu_exchange_data_for_attribute_value(request_t_apdu_jval, response_t_apdu_jval, attribute_id=24)
    if 'equOBUId' in attribute_value:
        equOBUId_hex = attribute_value['equOBUId'].upper()
        return equOBUId_hex

def search_for_pan_value_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval):
    attribute_value = search_json_t_apdu_exchange_data_for_attribute_value(request_t_apdu_jval, response_t_apdu_jval, attribute_id=32)

    if 'paymeans' in attribute_value:
        personalAccountNumber = attribute_value['paymeans']['personalAccountNumber'].upper()
        return personalAccountNumber

def search_for_gnss_status_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval):
    attribute_value = search_json_t_apdu_exchange_data_for_attribute_value(request_t_apdu_jval, response_t_apdu_jval, attribute_id=50)

    if 'gnssStatus' in attribute_value:
        return attribute_value['gnssStatus']

def verify_obe_authenticity(get_stamped_action_response_value=None):
    global last_response_t_apdu_value
    global last_vst_value

    if get_stamped_action_response_value is None:
        get_stamped_action_response_value = last_response_t_apdu_value[1]
    if 'responseParameter' not in get_stamped_action_response_value:
        # Not a GET_STAMPED.response!!
        return True
    if get_stamped_action_response_value['responseParameter'][0] != 'gstrs':
        # Not a GET_STAMPED.response!!
        return True

    get_stamped_rs = get_stamped_action_response_value['responseParameter'][1]

    # if 'get_stamped_response_value' not in locals():
    #     bcm_logger.error("No GET_STAMPED.response to verify!!")
    eid = get_stamped_action_response_value['eid']

    attributeList = get_stamped_rs['attributeList']
    bcm_logger.info(f'[OBE AUTH] attributeList value: {attributeList}')

    container_with_attribute_list = ('attrList', get_stamped_rs['attributeList'])

    bcm_logger.info(f"[OBE AUTH] EFC Container of Type/CHOICE 'attrList' value: {container_with_attribute_list}")
    efc_asn_compilation.EfcDsrcGeneric.EfcContainer.set_val(container_with_attribute_list)
    bcm_logger.info(f"[OBE AUTH] EFC Container of Type/CHOICE 'attrList' in ASN: {efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_asn1()}")

    attribute_list_bytes = efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_uper()[1:]

    provided_authenticator = get_stamped_rs['authenticator']
    bcm_logger.info(f"[OBE AUTH] Authenticator provided by OBE (UPER hex): {provided_authenticator.hex().upper()}")

    rnd_rse_bytes = rnd_rse_bytes_value
    rnd_rse_int = int.from_bytes(rnd_rse_bytes, 'big')

    pan_bytes = get_stamped_rs['attributeList'][0]['attributeValue'][1]['personalAccountNumber']

    bcm_logger.debug(f'[OBE AUTH] AttributeList: {attribute_list_bytes}')
    bcm_logger.debug(f'[OBE AUTH] RndRSE int: {rnd_rse_int}')

    if not SKIP_CONTRACT_DSRC_AUTH:
        obu_contract_ref = custom_its_per_decoders.get_obu_contract_ref_from_vst_value(eid, last_vst_value)
        td_name = tc_manage_toll_domains.get_current_toll_domain()
        norm = tc_manage_toll_domains.get_current_security_norm()
        authenticator = tc_dsrc_auth.compute_authenticator_with_device_contract_ref_and_auk_ref(pan_bytes, obu_contract_ref, attribute_list_bytes, rnd_rse_int, td_name, norm, 115)

        if provided_authenticator == authenticator:
            bcm_logger.info('[OBE AUTH] OK!!!')
            return True
            # raise Exception('[OBE AUTH] Invalid OBE Auth!!')
        else:
            bcm_logger.critical('[OBE AUTH] ERROR!!!')
            return False

def enrich_transaction_data(transaction_data_json, request_t_apdu_jval, response_t_apdu_jval):
    equOBUId_hex = search_for_obu_id_value_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval)
    if equOBUId_hex is not None:
        rename_transaction_data_file(equOBUId_hex)
        transaction_data_json['equOBUId'] = equOBUId_hex
    pan_hex = search_for_pan_value_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval)
    if pan_hex:
        transaction_data_json['personalAccountNumber'] = pan_hex
    gnss_status = search_for_gnss_status_in_t_apdu_exchange(request_t_apdu_jval, response_t_apdu_jval)
    if gnss_status:
        transaction_data_json['position_info'] = gnss_status

    valid_stamp = verify_obe_authenticity()
    transaction_data_json['obu_provided_invalid_attr_auth_stamp'] |= not valid_stamp

def add_t_apdu_data_to_transaction_data(request_t_apdu_jval, response_t_apdu_jval):
    global transaction_data_filepath
    if 'current_transaction_id' not in globals():
        bcm_logger.error(f'Cannot add DSRC transaction data to file without transaction init data')
        return

    # new_transaction_phase_data_json dict is a merge of the T-APDU request and response JSON values
    new_transaction_phase_data_json = request_t_apdu_jval | response_t_apdu_jval

    # Getting previous (initialization phase) transaction data
    with transaction_data_filepath.open('r') as json_file:
        transaction_data_json = json.load(json_file)
        transaction_data_json['data']['transaction_phase'].append(new_transaction_phase_data_json)

    enrich_transaction_data(transaction_data_json, request_t_apdu_jval, response_t_apdu_jval)

    # Rewriting transaction data file with new exchange data added
    # We also change the last_update_timestamp field
    with transaction_data_filepath.open('w') as json_file:
        transaction_data_json['last_update_timestamp'] = datetime.now().isoformat()
        json.dump(transaction_data_json, json_file, indent=2)
    return transaction_data_json

async def check_and_update_beacon_state():
    global current_beacon_name
    if 'current_beacon_name' not in globals():
        bcm_logger.critical('No beacon is set!! Please fix the RSE config for a beacon to be initialized properly via BAC L7.')
        raise NoBeaconInitialized('No beacon is set!! Please fix the RSE config for a beacon to be initialized properly via BAC L7.')

    await beacon_bac_l7_wrapper._pertel_get_communication_count()

    if current_beacon_name == 'TGBV':
        beacon_state = await beacon_bac_l7_wrapper.update_state()
        if beacon_state[1] == pertel_bac_l7.BCM_MODE_Enum.PERTEL_MODE_Stopped:
            raise BeaconManagerException("Beacon is in Stopped mode, not Transparent!!")
        bcm_logger.debug(f"Last BeaconID: {beacon_bac_l7_wrapper.get_beacon_id().hex().upper()}")
        return beacon_state
    elif current_beacon_name == 'OPS1955':
        pass

def get_init_data():
    global initialization_data

    if 'initialization_data' not in globals():
        return {}
    return initialization_data

def get_parameter_for_eid(eid):
    # Kapsch System Element: EID 0, no VST parameter
    if eid == 0:
        bcm_logger.info(f'Kapsch System Element has no Parameter in VST!!!')
        return b''
    return get_parameter_bytes_from_eid_on_vst_value(eid=eid)

def log_attribute_list_val_in_hex_uper_format(attribute_list):
    for attribute_pair in attribute_list:
        attr_id = attribute_pair['attributeId']
        attr_val = attribute_pair['attributeValue']
        EFCv5.EfcDsrcGeneric.EfcContainer.set_val(attr_val)
        attr_uper = EFCv5.EfcDsrcGeneric.EfcContainer.to_uper()

        # Decoded attribute value from T-APDU!
        t_apdu_uper_logger.info(f'attributeId ({attr_id}) val: 0x{attr_uper.hex().upper()}')

def log_attrs_in_get_resp_in_hex_uper_format(decoded_t_apdu_val):
    if 'actionResponse' == decoded_t_apdu_val[0]:
        if 'responseParameter' in decoded_t_apdu_val[1]:
            if 'gstrs' == decoded_t_apdu_val[1]['responseParameter'][0]:
                attribute_list = decoded_t_apdu_val[1]['responseParameter'][1]['attributeList']
                log_attribute_list_val_in_hex_uper_format(attribute_list)

    if 'attributelist' in decoded_t_apdu_val[1]:
        attribute_list = decoded_t_apdu_val[1]['attributelist']
        log_attribute_list_val_in_hex_uper_format(attribute_list)

class TApduResponseDecodeError(Exception):
    pass
def decode_t_apdu_response_uper(t_apdu_with_response_bytes):
    global TApdu_container
    global last_response_t_apdu_value
    global last_response_t_apdu_json

    bcm_logger.debug(f"Decoding received response T-APDU...")
    try:
        TApdu_container.from_uper(t_apdu_with_response_bytes)
    except pycrate_core.charpy.CharpyErr:
        bcm_logger.critical(f'[Pycrate UPER decoder] T-APDU response UPER decoding error!! T-APDU UPER hex value: {t_apdu_with_response_bytes.hex().upper()}')
        raise TApduResponseDecodeError('T-APDU response UPER decoding error!!')

    last_response_t_apdu_value = TApdu_container._val
    bcm_logger.debug(f"Response T-APDU value: {last_response_t_apdu_value}")
    log_attrs_in_get_resp_in_hex_uper_format(last_response_t_apdu_value)

    bcm_logger.info(f"Response T-APDU in ASN:\n{TApdu_container.to_asn1()}")
    # bcm_logger.debug(f"Response T-APDU decoded with JER:\n{TApdu_container.to_jer()}")
    last_response_t_apdu_json = TApdu_container._to_jval()
    # bcm_logger.debug(f"Response T-APDU in JSON: {last_response_t_apdu_json}")

    bcm_logger.debug(f"Checking if T-APDU contains a return (ret) value (error code)...")
    try:
        return_code = last_response_t_apdu_value[1]["ret"]
        if return_code == 0:
            bcm_logger.info(f"Return code is present and is 0! (No errors)")
            bcm_logger.debug(f"ReturnStatus ASN1 decoding:\n{efc_asn_compilation.EfcDsrcGeneric.ReturnStatus.to_asn1()}")
        else:
            bcm_logger.error(f"Error code present! Return Code: {return_code}")
            efc_asn_compilation.EfcDsrcGeneric.ReturnStatus.set_val(return_code)
            bcm_logger.error(f"ReturnStatus ASN1 decoding:\n{efc_asn_compilation.EfcDsrcGeneric.ReturnStatus.to_asn1()}")
            # if return_code == 1:
            #     raise TApduResponseException(f"Return Status: {efc_asn_compilation.EfcDsrcGeneric.ReturnStatus.to_asn1()}")
    except KeyError:
        bcm_logger.info(f"No return code in T-APDU! (No errors)")
    return last_response_t_apdu_value

def decode_vst_parameter_with_eid_only(eid):
    bcm_logger.debug(f"Decoding VST parameter with EID {eid}...")
    parameter_bytes = get_parameter_for_eid(eid)

    decoded_parameter = custom_its_per_decoders.decode_vst_parameter_oct_str_bytes(parameter_bytes)
    return decoded_parameter

def get_parameter_bytes_from_eid_on_vst_value(eid:int, vst_value=None) -> bytes:
    if vst_value is None:
        vst_value = last_vst_value
    return custom_its_per_decoders.get_parameter_bytes_from_vst_value_on_eid(eid, vst_value)

def get_obu_contract_ref_with_eid_only(eid:int, vst_value:dict=None):
    if not vst_value:
        vst_value = last_vst_value
    return custom_its_per_decoders.get_obu_contract_ref_from_vst_value(eid, vst_value)

def compute_access_credentials_for_eid(eid:int) -> bytes:
    bcm_logger.debug(f"Computing Access Credentials for EID {eid}...")
    decoded_vst_param = decode_vst_parameter_with_eid_only(eid)

    if len(decoded_vst_param) == 1:
        # VST parameter contains EFC-CM only, no AC_CR-KeyRef or RndOBE present
        # As such, we do not need any access credentials!
        return bytes(4)
    ac_cr_key_ref = decoded_vst_param['AC_CR-KeyReference']
    rnd_obe = decoded_vst_param['RndOBE']
    obu_contract_ref = get_obu_contract_ref_with_eid_only(eid)

    td_name = tc_manage_toll_domains.get_current_toll_domain()
    access_credentials_int = tc_dsrc_auth.compute_access_credentials_for_obu_on_td(obu_contract_ref, rnd_obe, ac_cr_key_ref, td_name=td_name)
    access_credentials_bytes = access_credentials_int.to_bytes(4, 'big')
    return access_credentials_bytes
    # except dsrc_security.TollDomainException:
    #     bcm_logger.error("TollDomainException occurred!", stack_info=True)

async def send_get_request(eid, accessCredentialsPresent:bool = False, attrIdList=None, close_transaction = False) -> AXXESv1_2.SEQ:
    if accessCredentialsPresent:
        accessCredentials = compute_access_credentials_for_eid(eid)
    else:
        accessCredentials = None
    # Get.Request is filled with 1 bit valued at 0
    get_req_value = {
        'eid': eid,
        'accessCredentials': accessCredentials,
        'attrIdList': attrIdList,
        'fill': (0, 1)
    }
    # Ignore keys in dict that map to None!!
    # That is, remove OPTIONAL elements that map to None
    # This is specially the case for the OPTIONAL accessCredentials
    get_req_value = {key: value for key, value in get_req_value.items() if value is not None}

    efc_asn_compilation.EfcDsrcGeneric.Get_Request.set_val(get_req_value)
    bcm_logger.debug(f"Get.Request value: {efc_asn_compilation.EfcDsrcGeneric.Get_Request._val}")

    t_apdu_with_get_request_value = ('getRequest', get_req_value)
    response_t_apdu_value = await send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_get_request_value, close_transaction=close_transaction)

    bcm_logger.debug("We now obtain the GET.response object from the T_APDU response!")
    bcm_logger.debug("GET.response is a parameterized type, so we cannot encode/decode it, only the T_APDU!")

    return response_t_apdu_value

# SET.request only exists for EFC, LAC UNI (AIDs 1, 20 and 29)! Not for CCC (AID 20).
async def send_set_request(eid, access_credentials:int, attrList, close_transaction=False):
    global TApdu_container
    aid = 1
    # SET.Request is filled with 1 bit valued at 0
    set_req_value = {
        'fill': (0, 1),
        'eid': eid,
        'mode': True,
        'accessCredentials': access_credentials,
        'attrList': attrList
    }

    bcm_logger.debug(f"SET.Request value: {set_req_value}")

    t_apdu_with_set_request_value = ('set-request', set_req_value)

    prev = TApdu_container
    TApdu_container = efc_asn_compilation.EfcDsrcGeneric.T_APDUs
    response_t_apdu_value = await send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_set_request_value, close_transaction=close_transaction)
    TApdu_container = prev

    bcm_logger.debug(f"SET.Response value: {efc_asn_compilation.EfcDsrcGeneric.T_APDUs._val[1]}")

    return response_t_apdu_value

async def send_set_request_with_eack_ac_cr(eid, attrList, close_transaction=False):
    accessCredentials = compute_access_credentials_for_eid(eid)
    # Get.Request is filled with 1 bit valued at 0
    set_req_value = {
        'eid': eid,
        'accessCredentials': accessCredentials,
        'attrList': attrList,
        'fill': (0, 1)
    }

    efc_asn_compilation.EfcDsrcGeneric.Set_Request.set_val(set_req_value)
    bcm_logger.debug(f"SET.Request value: {efc_asn_compilation.EfcDsrcGeneric.Set_Request._val}")

    t_apdu_with_get_request_value = ('setRequest', set_req_value)
    response_t_apdu_value = await send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_get_request_value, close_transaction=close_transaction)

    bcm_logger.debug(f"SET.Response value: {efc_asn_compilation.EfcDsrcGeneric.T_APDUs._val[1]}")

    return response_t_apdu_value

async def send_action_request(
        mode=True,
        eid=0,
        actionType=0xA,
        accessCredentialsPresent:bool = True,
        actionParameter = None,
        iid = None,
        close_transaction = False):
    global TApdu_container

    if accessCredentialsPresent:
        accessCredentials = compute_access_credentials_for_eid(eid)
    else:
        accessCredentials = None
    if not actionParameter:
        actionParameter = ('setmmirq', 0)
    bcm_logger.info(f"Preparing an ACTION.request with ActionType ({actionParameter[0]})")

    # ACTION.request has a parameter, which needs to be inside a container
    efc_asn_compilation.EfcDsrcGeneric.EfcContainer.set_val(actionParameter)
    parameter_tag = efc_asn_compilation.EfcDsrcGeneric.EfcContainer._tag

    bcm_logger.debug(f"ActionParameter is an EfcContainer of Type ({actionParameter[0]}) (tag {parameter_tag}) value decoded with JER:\n{efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_jer()}")
    bcm_logger.debug(f"Same value but APER-encoded in hex: {efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_aper().hex().upper()}")

    action_request_value = {
        'mode': mode,
        'eid': eid,
        'actionType': actionType,
        'accessCredentials': accessCredentials,
        'actionParameter': actionParameter,
        'iid': iid
        }
    bcm_logger.debug(f"ACTION.request value: {action_request_value}")

    # Ignore keys in dict that map to None!!
    # That is, remove OPTIONAL elements that map to None
    # This is specially the case for the OPTIONAL accessCredentials and iid
    action_request_value = {key: value for key, value in action_request_value.items() if value is not None}

    t_apdu_with_action_req_value = ('actionRequest', action_request_value)
    bcm_logger.debug(f"T-APDU with ACTION.request value: {t_apdu_with_action_req_value}")

    TApdu_container.set_val(t_apdu_with_action_req_value)
    bcm_logger.info(f"T-APDU with ACTION.request in ASN:\n{TApdu_container.to_asn1()}")
    bcm_logger.debug(f"ACTION.request with ActionType {actionType} and actionParameter of type {actionParameter[0]} being now sent...")

    response_t_apdu_value = await send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_action_req_value, close_transaction)
    return response_t_apdu_value

async def presentation_request(
        eid:int,
        accessCredentialsPresent:bool = True,
        attrIdList=[],
        operator_auk_ref=111,
        close_transaction=False):
    return await send_get_stamped_request(eid, accessCredentialsPresent, attrIdList, operator_auk_ref, close_transaction)

async def send_get_stamped_request(
        eid:int,
        accessCredentialsPresent:int = True,
        attrIdList=[],
        operator_auk_ref=111,
        close_transaction=False):
    global last_response_t_apdu_value

    bcm_logger.debug("Preparing an ActionParameter for an Action-Request of type GET_STAMPED.request (Presentation request)...")
    get_stamped_rq_value = get_stamped_request_action_parameter_preparation(eid, attrIdList, operator_auk_ref)

    bcm_logger.debug("Putting the GetStampedRq inside a 'gstrq' EFC Container...")
    container_with_get_stamped_rq_value = ('gstrq', get_stamped_rq_value)
    bcm_logger.debug(f"Container with GetStampedRq value: {container_with_get_stamped_rq_value}")

    # ActionType is 0 for GET_STAMPED.request and Mode is True (Always expects a response)
    response_t_apdu_value = await send_action_request(True, eid, 0, accessCredentialsPresent, container_with_get_stamped_rq_value, close_transaction=close_transaction)

    # custom_its_per_decoders.decode_get_response_param(response_t_apdu_value)

    return response_t_apdu_value

def get_stamped_request_action_parameter_preparation(eid:int, attrIdList:list = [], operator_auk_ref=111):
    """
    ACTION.request of type GET_STAMPED.request (ActionType=0).

    The ActionParameter is thus of type GetStampedRs
    """
    if not attrIdList:
        attrIdList = []

    bcm_logger.debug(f"Preparing a GET_STAMPED.request to get attributes with ids {attrIdList}")
    update_rnd_rse()

    get_stamped_rq_value = {
        'attributeIdList': attrIdList,
        'nonce': rnd_rse_bytes_value,
        'keyRef': operator_auk_ref
        }
    bcm_logger.debug(f"GetStampedRq value to be stored in definition: {get_stamped_rq_value}")
    efc_asn_compilation.EfcDsrcApplication.GetStampedRq.set_val(get_stamped_rq_value)

    bcm_logger.debug(f"GetStampedRq in ASN: {efc_asn_compilation.EfcDsrcApplication.GetStampedRq.to_asn1()}")
    # bcm_logger.info(f"GetStampedRs in JER:\n{efc_asn_compilation.EfcDsrcApplication.GetStampedRq.to_jer()}")
    return get_stamped_rq_value

async def send_echo_action_request(eid=0, text='Hello, World!', close_transaction=False):
    """EID should always be 0 for ECHO.request!!!"""
    bcm_logger.debug(f"Preparing an ECHO.request")

    echo_rq_value = ('octetstring', text.encode('utf-8'))

    efc_asn_compilation.EfcDsrcGeneric.EfcContainer.set_val(echo_rq_value)
    bcm_logger.debug(f"EfcContainer of Type 02 (OCTET STRING) value decoded with JER:\n{efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_jer()}")
    bcm_logger.debug(f"EfcContainer of Type 69 (OCTET STRING) value decoded with PER: {efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_uper()}")

    # ActionType is 15 or 0xF for ECHO.request
    echo_action_request_val = {
        'mode': True,
        'eid': 0,
        'actionType': 0xF,
        'actionParameter': echo_rq_value
        }
    t_apdu_with_echo_action_req_value = ('actionRequest', echo_action_request_val)
    bcm_logger.info(f"ACTION.request of Type 15 (ECHO) being now sent...")

    response_t_apdu_json = await send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_echo_action_req_value, close_transaction=close_transaction)
    # response_t_apdu_json = send_action_request(mode=True, eid=eid, actionType=15, accessCredentialsPresent=False, actionParameter=echo_rq_value, close_transaction=close_transaction)
    return response_t_apdu_json

async def set_mmi(eid=0, close_transaction=False):
    bcm_logger.debug(f"Preparing a SET_MMI.request")
    bcm_logger.debug(f"The function to send ACTION.requests is defined to send a SET_MMI by default if no arguments are provided!")

    set_mmi_request_value = 0
    # SetMMI is a parameterized type, so it needs to be inside a container
    set_mmi_efc_container_value = ('setmmirq', set_mmi_request_value)
    efc_asn_compilation.EfcDsrcGeneric.EfcContainer.set_val(set_mmi_efc_container_value)
    bcm_logger.debug(f"EfcContainer of Type 69 (SET_MMI) value decoded with JER:\n{efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_jer()}")
    bcm_logger.debug(f"EfcContainer of Type 69 (SET_MMI) value decoded with PER: {efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_uper()}")

    # SetMMI ActionType is 0xA, or 10 in decimal
    set_mmi_action_request_val = {
        'mode': True,
        'eid': eid,
        'actionType': 0xA,
        'actionParameter': set_mmi_efc_container_value
        }

    t_apdu_with_set_mmi_action_req_value = ('actionRequest', set_mmi_action_request_val)
    bcm_logger.info(f"ACTION.request of Type 10 (SET_MMI) being now sent...")

    t_apdu_with_action_response = await send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_set_mmi_action_req_value, close_transaction)
    return t_apdu_with_action_response

async def send_close_transaction_echo(eid=0, text="Hello, World!"):
    try:
        return await send_echo_action_request(eid=eid, text=text, close_transaction=True)
    except ObuResponseTimeout as exc:
        bcm_logger.error('OBU response timeout during SET_MMI request!')
        # We optionally ignore OBU response timeouts during SET_MMI requests!
        if not beacon_manager_config[current_beacon_name]['bac_l2_config']['IGNORE_OBU_TIMEOUTS_WHEN_CLOSING_TRANSACTION']:
            raise exc

async def send_close_transaction_setmmi(eid=0):
    try:
        return await set_mmi(eid, close_transaction=True)
    except ObuResponseTimeout as exc:
        bcm_logger.error('OBU response timeout during SET_MMI request!')
        # We optionally ignore OBU response timeouts during SET_MMI requests!
        if not beacon_manager_config[current_beacon_name]['bac_l2_config']['IGNORE_OBU_TIMEOUTS_WHEN_CLOSING_TRANSACTION']:
            raise exc

async def send_close_transaction_setmmi_if_transaction_open(eid=0):
    if beacon_bac_l7_wrapper._is_transaction_in_progress():
        return
    return await send_close_transaction_setmmi(eid)