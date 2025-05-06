import sys
import time

from ASN.compiled_DSRC_instances import AXXESv1_2
# from ASN.compiled_DSRC_instances import EFCv5
EFCv5 = AXXESv1_2
from ASN.compiled_DSRC_instances import CCCv1
# from ASN.compiled_DSRC_instances import LACv2_1 as efc_asn_compilation

efc_asn_compilation = AXXESv1_2

from datetime import datetime
import json
import logging
import uuid

import typing

from bac_l7 import ops1955_bac_l7, pertel_bac_l7, tgbv_bac_l7

import custom_its_per_decoders
from dsrc_security import dsrc_auth

bcm_logger = logging.getLogger(__name__)

local_transactions_storage_path_str = 'local_file_storage/transactions'
date_prefix = datetime.now().strftime('%y%m%d')

# SETTING UP LOGGER FILE HANDLER
file_handler = logging.FileHandler(f'beacon_logs/{date_prefix}_rse_dsrc_l7.log')
file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)
bcm_logger.addHandler(file_handler)

# Setting globals
## Garbage unsafe temporary globals
keep_looping = False

## Beacon L7 necessary values
beacon_bac_l7_wrapper = None

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
    await update_beacon_state()

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

# Start sending a BST
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
    bcm_logger.info(f"T_APDU containing BST (UPER hex): {TApdu_container.to_uper().hex().upper()}")

    fragmented_t_apdu = frag_header + last_sent_t_apdu_containing_bst
    bcm_logger.info(f"RSE is now emitting BST and awaiting VST from OBE...")
    response = await beacon_bac_l7_wrapper._pertel_start_bst_emission_and_await_vst(fragmented_t_apdu)

    if response[1] == 2:
        bcm_logger.critical("Transaction unclosed!!")
        await send_close_transaction_echo()
        exit()

    bcm_logger.debug("We now get the lastest BeaconID just after starting the BST")

    await update_beacon_state()

    return initialization_request_jval

async def initialize_transaction(
        manufacturer_id=0x31,
        individual_id=0x111,
        mand_applications=[1, 20, 29],
        profile=0x00,
        profile_list=[0x00],
        non_mand_applications = []
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

    await update_beacon_state()

    if beacon_bac_l7_wrapper._is_transaction_in_progress():
        bcm_logger.error("Do not try to initilize a transaction! One is already in progress!")
        # bcm_logger.debug("We lock the thread until the opened transaction is closed!")
        raise BeaconManagerException("Transaction already in progress!!")

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

    initialization_request_jval = await start_bst_emission_and_await_vst(bst_value=bst_value)

    bcm_logger.info("A VST was received!")
    fragmented_t_apdu_init_resp_datagram = beacon_bac_l7_wrapper.get_vst()
    bcm_logger.debug(f"Fragmented T_APDU containing VST (UPER hex): {fragmented_t_apdu_init_resp_datagram.hex().upper()}")

    bcm_logger.debug("We now remove the fragmentation header and instantiate an T_APDU object from the response!")
    t_apdu_init_resp_datagram = bytes(fragmented_t_apdu_init_resp_datagram[1:])
    bcm_logger.debug(f"T-APDU without fragmentation header (UPER hex): {t_apdu_init_resp_datagram.hex().upper()}")

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

    return (initialization_request_jval, last_response_t_apdu_json)

async def update_beacon_state():
    global current_beacon_name
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

    try:
        return initialization_data
    except:
        return {}

def find_eid_with_accepted_contract():
    eid = None
    return eid

def get_efc_cm_for_eid(eid):
    # Kapsch System Element: EID 0, no VST parameter
    if eid == 0:
        bcm_logger.info(f'Kapsch System Element has no Parameter in VST!!!')
        return {}
    return get_parameter_bytes_from_eid_on_vst_value(eid=eid)

def decode_t_apdu_response_uper(t_apdu_with_response_bytes):
    global TApdu_container
    global last_response_t_apdu_value
    global last_response_t_apdu_json

    bcm_logger.debug(f"Decoding received response T-APDU...")
    TApdu_container.from_uper(t_apdu_with_response_bytes)
    last_response_t_apdu_value = TApdu_container._val
    bcm_logger.debug(f"Response T-APDU value: {last_response_t_apdu_value}")

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

async def send_req_t_apdu_and_obtain_resp_t_apdu(asn1_request_t_apdu_value, close_transaction=False) -> dict:
    global TApdu_container
    if close_transaction:
        bcm_logger.info(f"Closing Transaction!! Info: BAC L2 command for closing a transaction is 0x06.")

    bcm_logger.debug(f"Preparing request T-APDU to be sent...")
    TApdu_container.set_val(asn1_request_t_apdu_value)
    bcm_logger.info(f"Request T-APDU value: {TApdu_container._val}")

    # Needed to store transaction data as JSON!
    request_t_apdu_jval = TApdu_container._to_jval()

    fragmented_t_apdu_request = frag_header + TApdu_container.to_uper()

    # Sending command!!!
    bac_l2_response = (await beacon_bac_l7_wrapper
        ._pertel_send_dsrc_l7_command_with_close_transaction_option(
            fragmented_t_apdu_request,
            close_transaction
            )
    )
    bac_l2_error_code = bac_l2_response[1]
    if bac_l2_error_code != 0:
        if bac_l2_error_code == 0x09:
            raise Exception('[BAC L2] Timeout OBE (0x09) received!!')
        raise Exception(f'[BAC L2] Error code (0x{bac_l2_error_code:02X}) present in BAC L2 response!!')
    beacon_bac_l7_wrapper.last_t_apdu_response_datagram
    fragmented_t_apdu_with_response_bytes = beacon_bac_l7_wrapper.last_t_apdu_response_datagram
    bcm_logger.info(f"Fragmented T-APDU response obtained from beacon in hex (UPER hex): {fragmented_t_apdu_with_response_bytes.hex().upper()}")

    try:
        t_apdu_with_response_bytes = bytes(fragmented_t_apdu_with_response_bytes[1:])

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

    current_transaction_id = uuid.uuid1()
    transaction_data_filename = f"local_file_storage/transactions/{current_transaction_id}.json"

    # initialization_data dict is a merge of the init request and response JSON values
    # initialization_data = initialization_request_jval | initialization_response_jval
    initialization_data = {}
    initialization_data['_id'] = current_transaction_id.hex

    # Merging initialisationRequest json into initialization_data json dict
    initialization_data |= initialization_request_jval

    # Merging initialisationResponse json into initialization_data json dict
    initialization_data |= initialization_response_jval

    # Create an empty list for future data exchanges (ACTION/GET/SET requests...)
    initialization_data["exchanged_data"] = []

    with open(transaction_data_filename, 'w') as json_file:
        initialization_data['creation_time'] = datetime.now().isoformat()
        json.dump(initialization_data, json_file, indent=2)
    return initialization_data

def add_t_apdu_data_to_transaction_data(request_t_apdu_jval, response_t_apdu_jval):
    global current_transaction_id
    transaction_data_filename = f"local_file_storage/transactions/{current_transaction_id}.json"

    # current_exchanged_data_json = {}
    # Adding T-APDU with request data to current exchange dict
    # current_exchanged_data_json |= request_t_apdu_jval

    # Adding T-APDU with response data to current exchange dict (dict merge)
    # current_exchanged_data_json |= response_t_apdu_jval

    # current_exchanged_data_json dict is a merge of the T-APDU request and response JSON values
    current_exchanged_data_json = request_t_apdu_jval | response_t_apdu_jval

    # Getting previous data
    with open(transaction_data_filename, 'r') as json_file:
        transaction_data_json = json.load(json_file)
        transaction_data_json['exchanged_data'].append(current_exchanged_data_json)

    # Rewriting transaction data file with current exchange data added
    # We also change the last_update_timestamp field
    with open(transaction_data_filename, 'w') as json_file:
        transaction_data_json['last_update_timestamp'] = datetime.now().isoformat()
        json.dump(transaction_data_json, json_file, indent=2)
    return transaction_data_json

def decode_vst_parameter_from_eid(eid):
    bcm_logger.debug(f"Decoding VST parameter with EID {eid}...")
    parameter_bytes = get_efc_cm_for_eid(eid)

    decoded_parameter = custom_its_per_decoders.decode_vst_parameter_oct_str_bytes(parameter_bytes)
    return decoded_parameter

def get_parameter_bytes_from_eid_on_vst_value(eid:int, vst_value=None) -> bytes:
    if vst_value is None:
        vst_value = last_vst_value
    bcm_logger.debug(f"Getting bytes VST parameter for EID {eid} from VST value {vst_value}")
    for application in vst_value['applications']:
        bcm_logger.debug(f"Application details: {application}")
        if application['eid'] == eid:
            parameter_value = application['parameter'][1]
            bcm_logger.info(f"Found EID {eid} in VST!!! Parameter value in hex: {parameter_value.hex().upper()}")
            return parameter_value
    bcm_logger.error(f"EID {eid} is not present!")
    raise EIDNotFoundException(f'L7: EID {eid} not present!')

def compute_access_credentials(eid:int) -> bytes:
    bcm_logger.debug(f"Computing Access Credentials for EID {eid}...")
    decoded_vst_param = decode_vst_parameter_from_eid(eid)

    efc_cm = decoded_vst_param['EFC-ContextMark']
    ac_cr_key_ref = decoded_vst_param['AC_CR-KeyReference']
    rnd_obe = decoded_vst_param['RndOBE']

    access_credentials_int = dsrc_auth.compute_access_credentials(efc_cm, rnd_obe, ac_cr_key_ref)
    access_credentials_bytes = access_credentials_int.to_bytes(4, 'big')
    return access_credentials_bytes
    # except dsrc_security.TollDomainException:
    #     bcm_logger.error("TollDomainException occurred!", stack_info=True)

async def send_get_request(eid, accessCredentialsPresent:bool = False, attrIdList=None, close_transaction = False) -> AXXESv1_2.SEQ:
    if accessCredentialsPresent:
        accessCredentials = compute_access_credentials(eid)
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
        accessCredentials = compute_access_credentials(eid)
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

    bcm_logger.debug("We now obtain the GET_STAMPED.response object from the T_APDU response!")
    bcm_logger.debug("GET_STAMPED.response is a parameterized type, so we cannot encode/decode it, only the T_APDU!")

    bcm_logger.debug("We now obtain the GetStampedRq object in the ACTION.Response's parameter!")
    bcm_logger.debug("GET_STAMPED.response is a parameterized type, so we cannot encode/decode it, only the T_APDU!")

    action_response_parameter = last_response_t_apdu_value[1]['responseParameter']
    get_stamped_response_value = action_response_parameter[1]
    bcm_logger.info(f'GetStampedRq value: {get_stamped_response_value}')

    bcm_logger.debug(f"GET_STAMPED.response (Presentation response): {response_t_apdu_value['actionResponse']['responseParameter']}")

    try:
        verify_obe_authenticity()
    except:
        bcm_logger.exception("OBE AUTH ERROR!!!", stack_info=True)
    return response_t_apdu_value

def verify_obe_authenticity(get_stamped_action_response_value=None):
    global last_response_t_apdu_value
    global last_vst_value

    if get_stamped_action_response_value is None:
        get_stamped_action_response_value = last_response_t_apdu_value[1]
    try:
        get_stamped_rs = get_stamped_action_response_value['responseParameter'][1]
    except KeyError:
        bcm_logger.error('[OBE AUTH] No responseParameter in GET_STAMPED.response!!!')
        return

    # if 'get_stamped_response_value' not in locals():
    #     bcm_logger.error("No GET_STAMPED.response to verify!!")
    eid = get_stamped_action_response_value['eid']
    decoded_vst_param = decode_vst_parameter_from_eid(eid)
    efc_cm = decoded_vst_param['EFC-ContextMark']

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

    bcm_logger.debug(f'[OBE AUTH] EFC-CM: {efc_cm}')
    bcm_logger.debug(f'[OBE AUTH] AttributeList: {attribute_list_bytes}')
    bcm_logger.debug(f'[OBE AUTH] RndRSE int: {rnd_rse_int}')

    manufacturer_id_int = last_vst_value['obeConfiguration']['manufacturerID']
    manufacturer_id_hex = f'{manufacturer_id_int:04X}'

    equipment_class_int = last_vst_value['obeConfiguration']['equipmentClass']
    equipment_class_hex = f'{equipment_class_int:04X}'

    authenticator = dsrc_auth.compute_authenticator_with_device_info_and_auk_ref(pan_bytes, efc_cm, manufacturer_id_hex, equipment_class_hex, attribute_list_bytes, rnd_rse_int, 115)

    if provided_authenticator == authenticator:
        bcm_logger.info('[OBE AUTH] OK!!!')
        return True
        # raise Exception('[OBE AUTH] Invalid OBE Auth!!')
    else:
        bcm_logger.critical('[OBE AUTH] ERROR!!!')

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
    set_mmi_action_request_val = {
        'mode': True,
        'eid': 0,
        'actionType': 0xF,
        'actionParameter': echo_rq_value
        }
    t_apdu_with_echo_action_req_value = ('actionRequest', set_mmi_action_request_val)
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
    return await send_echo_action_request(eid=eid, text=text, close_transaction=True)

async def send_close_transaction_setmmi(eid=0):
    return await set_mmi(eid, close_transaction=True)

async def cardme_transaction(eid, mand_applications=[1, 20, 29], accessCredentialsPresent=False, set_mmi=True):
    await initialize_transaction(mand_applications=mand_applications)
    # Getting payment info!! (Core part)
    await presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    # Getting Receipt data...
    # send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[33, 34])

    # Getting contract information...
    # send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[4])

    # Getting Vehicle attributes...
    ## Getting LPN only first case errors occurs in the 'big' GET.request
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[17, 18, 19, 20, 22])

    # Getting OBE info...
    # send_get_request(eid, False, attrIdList=[24, 25, 26])
    await send_get_request(eid, False, attrIdList=[24]) # Get equOBUId

    # Getting driver info...
    # send_get_request(eid, False, attrIdList=[27, 47])

    # Close the transaction
    if set_mmi == True:
        await send_close_transaction_setmmi(eid=eid)
    else:
        await send_close_transaction_echo(eid=eid)

async def tis_vl_transaction(eid, mand_applications=[1, 20, 29], accessCredentialsPresent=False, set_mmi=True):
    """
    Used in the context of TIS VL CIP CARDME/Liber-t transactions.
    TIS: Télépéage Inter Sociétés
    CIP: Commission Interautoroutes Péage
    VL: Véhicule Léger
    """
    initialize_transaction(mand_applications=mand_applications)
    presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[17, 18, 19, 20, 22])

    # Getting TIS specific/reserved attributes...
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[125, 126])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[95, 96])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[97, 98, 99])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=list(range(100, 104)))
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=list(range(104, 108)))
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=list(range(108, 112)))
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=list(range(112, 116)))
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await send_close_transaction_setmmi(eid=eid)
    else:
        await send_close_transaction_echo(eid=eid)

async def test_ccc_2009_transaction(eid, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    global efc_asn_compilation
    # Compiled CCC 2015 specs
    efc_asn_compilation = CCCv1

    await initialize_transaction(mand_applications=mand_applications)
    await presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # OBU ID
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC 2009 attributes...
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[48])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[49])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[50])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[51])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[52])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])

    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await send_close_transaction_setmmi(eid=eid)
    else:
        await send_close_transaction_echo(eid=eid)
    efc_asn_compilation = AXXESv1_2

async def test_ccc_2009_transaction_old(eid, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    global efc_asn_compilation
    # Compiled CCC 2015 specs
    efc_asn_compilation = CCCv1

    initialize_transaction(mand_applications=mand_applications)
    presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # OBU ID
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC 2009 attributes...
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[37])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[38])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[39])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[40])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[41])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[42])

    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await send_close_transaction_setmmi(eid=eid)
    else:
        await send_close_transaction_echo(eid=eid)
    efc_asn_compilation = AXXESv1_2

async def ccc_2015_status_history_transaction(eid, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    global efc_asn_compilation
    # Compiled CCC 2015 specs
    efc_asn_compilation = EFCv5

    initialize_transaction(mand_applications=mand_applications)
    presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    # OBU ID
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC attributes...
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[55])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[60])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[61])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[62])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[63])

    # Close the transaction
    if set_mmi == True:
        await send_close_transaction_setmmi(eid=eid)
    else:
        await send_close_transaction_echo(eid=eid)
    efc_asn_compilation = AXXESv1_2

async def test_ccc_2015_transaction(eid, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    global efc_asn_compilation
    # Compiled CCC 2015 specs
    efc_asn_compilation = EFCv5

    initialize_transaction(mand_applications=mand_applications)
    presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # Get OBU ID
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC attributes...
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[46])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[48])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[49])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[50])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[51])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[52])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[55])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[60])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[61])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[62])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[63])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[64])

    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await send_close_transaction_setmmi(eid=eid)
    else:
        await send_close_transaction_echo(eid=eid)
    efc_asn_compilation = AXXESv1_2

async def ccc_2023_transaction(eid, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    await initialize_transaction(mand_applications=mand_applications)
    await presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # Get OBU ID
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC attributes...
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[99])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[100])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[101])

    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await send_close_transaction_setmmi(eid=eid)
    else:
        await send_close_transaction_echo(eid=eid)

async def kapsch_system_element_transaction(eid=0, mand_applications=[0], accessCredentialsPresent=True, set_mmi=True):
    initialize_transaction(mand_applications=mand_applications)
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[1, 2, 3])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[6, 7])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[10])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[17])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[18])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[23])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[33])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[108])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[120])

    # Close the transaction
    if set_mmi == True:
        await send_close_transaction_setmmi(eid=eid)
    else:
        await send_close_transaction_echo(eid=eid)

async def test_transaction(eid, mand_applications=[1, 20, 29], accessCredentialsPresent=False, set_mmi=True):
    initialize_transaction(mand_applications=mand_applications)
    presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # Getting CCC attributes...
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[99])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[100])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[101])

    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[111, 115, 118])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])
    await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[125, 126])

    # Close the transaction
    if set_mmi == True:
        await send_close_transaction_setmmi(eid=eid)
    else:
        await send_close_transaction_echo(eid=eid)

async def get_all_attributes(eid, mand_applications=[1, 20, 29]):
    attrIdList = list(range(0, 128))
    return await get_attributes_in_list(eid, attrIdList, mand_applications=mand_applications)

async def get_attributes_in_list(eid, accessCredentialsPresent=True, attrIdList=[32], mand_applications=[1, 20, 29], set_mmi=False):
    global last_response_t_apdu_json

    # Initialize transaction
    initialize_transaction(mand_applications=mand_applications)

    # Send GET.requests
    obtained_attrs = set()
    get_responses = []
    try:
        for attr in attrIdList:
            await send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[attr])
            try:
                if last_response_t_apdu_json['getResponse']['ret'] == 0:
                    bcm_logger.info(last_response_t_apdu_json['getResponse'])
                    obtained_attrs.add(attr)
                    get_responses.append(last_response_t_apdu_json['getResponse']['attributelist'])
            except KeyError:
                bcm_logger.info(last_response_t_apdu_json['getResponse'])
                obtained_attrs.add(attr)
                get_responses.append(last_response_t_apdu_json['getResponse']['attributelist'])
    except EIDNotFoundException:
        bcm_logger.error("EID not present!", stack_info=True)
    bcm_logger.info(f"Obtained attributes: {obtained_attrs}")
    bcm_logger.info(f"Rejected attributes: {set(attrIdList).difference(obtained_attrs)}")

    bcm_logger.info(json.dumps(get_responses, indent=2))

    # Close the transaction
    if set_mmi == True:
        await send_close_transaction_setmmi(eid=eid)
    else:
        await send_close_transaction_echo(eid=eid)

    return obtained_attrs, get_responses

def stop_loop():
    global keep_looping
    keep_looping = False

def set_beeping_state(beep_state=False):
    global loop_set_mmi_bool
    loop_set_mmi_bool = beep_state

def loop_transactions():
    global keep_looping
    global loop_set_mmi_bool
    if keep_looping == True:
        bcm_logger.error('Loop already in progress!!')
        return
    keep_looping = True
    if 'loop_set_mmi_bool' not in globals():
        loop_set_mmi_bool = False

    while keep_looping:
        try:
            get_attributes_in_list(eid=4, attrIdList=[32], mand_applications=[1, 20], set_mmi=loop_set_mmi_bool)
            time.sleep(0.3)

            get_attributes_in_list(eid=2, attrIdList=[16, 17, 18, 19, 20, 22, 32], mand_applications=[1, 20], set_mmi=False)
            time.sleep(0.01)
            get_attributes_in_list(eid=2, attrIdList=[50, 51, 52], mand_applications=[1, 20], set_mmi=False)
            get_attributes_in_list(eid=2, attrIdList=[53, 99, 100, 101], mand_applications=[1, 20], set_mmi=False)
            time.sleep(0.3)

            get_attributes_in_list(eid=3, attrIdList=[16, 17, 18, 19, 20, 22, 32], mand_applications=[1, 20])
            time.sleep(0.01)
            get_attributes_in_list(eid=3, attrIdList=[50, 51, 52], mand_applications=[1, 20], set_mmi=False)
            get_attributes_in_list(eid=3, attrIdList=[53, 99, 100, 101], mand_applications=[1, 20], set_mmi=False)
            time.sleep(0.3)

            time.sleep(3)
        except UnclosedTransactionException:
            keep_looping = False
            bcm_logger.error("Transaction error occurred during loop!", exc_info=True)
            time.sleep(1)