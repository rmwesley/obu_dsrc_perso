import sys

from datetime import datetime
import json
import logging
import asyncio
import typing
from typing_extensions import Any

import pycrate_core.charpy
from pycrate_asn1rt.asnobj_construct import CHOICE

from axxes_asn_compiles.ASN.compiled_DSRC_instances import AXXESv1_2
from custom_its_decoders import custom_its_per_decoders

from ..globals import LOG_DIR, SETTINGS_DIR
from ..bac_l7 import ops1955_bac_l7, pertel_bac_l7, tgbv_bac_l7
from ..toll_charging_security import tc_dsrc_auth, tc_manage_toll_domains
from ..dsrc_transactions import disk_transaction_persistence

# from ASN.compiled_DSRC_instances import EFCv5
EFCv5 = AXXESv1_2
# from ASN.compiled_DSRC_instances import CCCv1
# from ASN.compiled_DSRC_instances import LACv2_1 as efc_asn_compilation

efc_asn_compilation = AXXESv1_2

# File logger, so prevent propagation!!
rse_dsrc_l7_logger = logging.getLogger(__name__)
rse_dsrc_l7_logger.setLevel(logging.DEBUG)
rse_dsrc_l7_logger.propagate = False

# File loggers, so prevent propagation!!
t_apdu_uper_logger = logging.getLogger('T_APDU_logger')
t_apdu_uper_logger.setLevel(logging.INFO)
t_apdu_uper_logger.propagate = False

startup_date = datetime.now()
logs_date_prefix = startup_date.strftime('%y%m%d')

# SETTING UP LOGGER FILE HANDLER
rse_l7_logs_path = LOG_DIR / f'beacon_logs/{logs_date_prefix}_rse_dsrc_l7.log'
rse_l7_logs_path.parent.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(rse_l7_logs_path)
file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)
rse_dsrc_l7_logger.addHandler(file_handler)

rse_uper_logs_path = LOG_DIR / f'beacon_logs/{logs_date_prefix}_rse_t_apdu_uper.log'
t_apdu_file_handler = logging.FileHandler(rse_uper_logs_path)
t_apdu_file_handler.setFormatter(file_formatter)
t_apdu_uper_logger.addHandler(t_apdu_file_handler)

# Setting globals
## Garbage unsafe temporary globals
keep_looping = False

BCM_CONF_FILENAME = "bcm_config.json"

## SKIP DSRC AUTH
SKIP_CONTRACT_DSRC_AUTH = False

def log_attribute_list_val_in_hex_uper_format(attribute_list, attr_container:CHOICE):
    for attribute_pair in attribute_list:
        attr_id = attribute_pair['attributeId']
        attr_val = attribute_pair['attributeValue']
        attr_container.set_val(attr_val)
        attr_uper:bytes = attr_container.to_uper()

        # Decoded attribute value from T-APDU!
        t_apdu_uper_logger.info(f'attributeId ({attr_id}) val: 0x{attr_uper.hex().upper()}')

def log_attrs_in_get_resp_in_hex_uper_format(decoded_t_apdu_val, attr_container:CHOICE):
    if 'actionResponse' == decoded_t_apdu_val[0]:
        if 'responseParameter' in decoded_t_apdu_val[1]:
            if 'gstrs' == decoded_t_apdu_val[1]['responseParameter'][0]:
                attribute_list = decoded_t_apdu_val[1]['responseParameter'][1]['attributeList']
                log_attribute_list_val_in_hex_uper_format(attribute_list, attr_container)

    if 'attributelist' in decoded_t_apdu_val[1]:
        attribute_list = decoded_t_apdu_val[1]['attributelist']
        log_attribute_list_val_in_hex_uper_format(attribute_list, attr_container)

def pdu_to_frag_header(pdu:int|None):
    if type(pdu) is not int:
        raise ValueError("PDU must be an integer")
    if pdu > 0xF:
        raise ValueError("PDU must be at most 4 bits!!")
    if pdu == 0 or pdu == 1:
        raise ValueError("PDU cannot be 0 or 1!!")
    # PDU is at most 4 bits
    pdu &= 0xF
    # The fragmentation header is 0b1xxxx001, where xxxx is the PDU
    # 0b10000001 = 0x81
    frag_header = bytes([0x81 | (pdu << 3)]) # 0x91, since pdu=0x2
    return frag_header

def get_rse_driver(beacon_name):
    """Get the beacon driver for beacon_name"""
    if beacon_name == 'TGBV':
        bac_l7_driver = tgbv_bac_l7.TgbvBacL7()
        return bac_l7_driver

    if beacon_name == 'OPS1955':
        bac_l7_driver = ops1955_bac_l7.Ops1955BacL7()
        asyncio.run(bac_l7_driver.kapsch_set_config_from_settings())

        return bac_l7_driver
    raise ValueError(f"Unknown beacon_name {beacon_name}: RSE driver not found!")

async def close_and_update_bac_l7_driver(
        current_driver:pertel_bac_l7.PertelBacL7|None,
        beacon_name:str,
    ):
    """Close the current RSE driver, and get the new beacon driver from its name"""
    rse_dsrc_l7_logger.info(f'Setting RSE driver to ({beacon_name})')

    if current_driver is not None:
        current_driver.close()

    return get_rse_driver(beacon_name)

RSE_DRIVERS_DIR = SETTINGS_DIR / "rse_drivers"
def load_config(beacon_name) -> dict[str, typing.Any]:
    with ( RSE_DRIVERS_DIR / f"{beacon_name}.json" ).open('r') as bcm_cfg_file:
        bcm_config = json.load(bcm_cfg_file)
    return bcm_config

def pertel_beacon_state_description(beacon_state:bytes):
    return {
            'state': beacon_state[0],
            'mode': beacon_state[1],
            'trxInProgress': beacon_state[2]
            }

def compute_rnd_rse_from_session_time():
    rse_dsrc_l7_logger.debug(f"Updating DateAndTime/SessionTime value (to be used as RndRSE value)...")

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

    rse_dsrc_l7_logger.debug(f"RndRSE or SessionTime value (of type DateAndTime) in ASN:\n{efc_asn_compilation.EfcDataDictionary.DateAndTime.to_asn1()}")
    rnd_rse_bytes_val:bytes = efc_asn_compilation.EfcDataDictionary.DateAndTime.to_uper()
    setattr(sys.modules[__name__], "rnd_rse_bytes_value", rnd_rse_bytes_val)

    rse_dsrc_l7_logger.debug(f"RndRSE value (UPER hex): {rnd_rse_bytes_val.hex().upper()}")
    return rnd_rse_bytes_val


def verify_obe_auth(last_vst_val, get_st_act_rs_val, rnd_rse_val, attr_container:CHOICE):
    if 'responseParameter' not in get_st_act_rs_val:
        # Not a GET_STAMPED.response!!
        return False
    if get_st_act_rs_val['responseParameter'][0] != 'gstrs':
        # Not a GET_STAMPED.response!!
        return False

    get_stamped_rs = get_st_act_rs_val['responseParameter'][1]

    # if 'get_stamped_response_value' not in locals():
    #     bcm_logger.error("No GET_STAMPED.response to verify!!")
    eid = get_st_act_rs_val['eid']

    attributeList = get_stamped_rs['attributeList']
    rse_dsrc_l7_logger.info(f'[OBE AUTH] attributeList value: {attributeList}')

    container_with_attribute_list = ('attrList', get_stamped_rs['attributeList'])

    rse_dsrc_l7_logger.info(f"[OBE AUTH] EFC Container of Type/CHOICE 'attrList' value: {container_with_attribute_list}")
    attr_container.set_val(container_with_attribute_list)
    rse_dsrc_l7_logger.info(f"[OBE AUTH] EFC Container of Type/CHOICE 'attrList' in ASN: {attr_container.to_asn1()}")

    attribute_list_bytes:bytes = attr_container.to_uper()[1:]

    provided_authenticator = get_stamped_rs['authenticator']
    rse_dsrc_l7_logger.info(f"[OBE AUTH] Authenticator provided by OBE (UPER hex): {provided_authenticator.hex().upper()}")

    rnd_rse_int = int.from_bytes(rnd_rse_val, 'big')

    pan_bytes = get_stamped_rs['attributeList'][0]['attributeValue'][1]['personalAccountNumber']

    rse_dsrc_l7_logger.debug(f'[OBE AUTH] AttributeList: {attribute_list_bytes}')
    rse_dsrc_l7_logger.debug(f'[OBE AUTH] RndRSE int: {rnd_rse_int}')

    if not SKIP_CONTRACT_DSRC_AUTH:
        obu_contract_ref = custom_its_per_decoders.get_obu_contract_ref_from_vst_value(eid, last_vst_val)
        td_name = tc_manage_toll_domains.get_current_toll_domain()
        norm = tc_manage_toll_domains.get_current_security_norm()
        authenticator = tc_dsrc_auth.compute_authenticator_with_device_contract_ref_and_auk_ref(pan_bytes, obu_contract_ref, attribute_list_bytes, rnd_rse_int, td_name, norm, 115)

        if provided_authenticator == authenticator:
            rse_dsrc_l7_logger.info('[OBE AUTH] OK!!!')
            return True
            # raise Exception('[OBE AUTH] Invalid OBE Auth!!')
        else:
            rse_dsrc_l7_logger.critical('[OBE AUTH] ERROR!!!')
            return False


class BeaconManagerException(Exception):...
class UnclosedTransactionException(Exception): ...
class TApduResponseException(Exception): ...
class EIDNotFoundException(Exception): ...
class AbortedInitPhase(Exception): ...
class NoBeaconInitialized(Exception): ...

class ObuResponseTimeout(Exception): ...
class CommandRefused(Exception): ...

class TApduResponseDecodeError(Exception):...

class RseDsrcL7App():
    def __init__(self,
            pdu:int|None,
            beacon_name:str,
            t_apdu_container:CHOICE
        ) -> None:
        """pdu=None sets it to default 0x02"""
        self.frag_header                              = pdu_to_frag_header(pdu)
        self.bcm_config:dict                          = load_config(beacon_name)
        self.t_apdu_container:CHOICE                  = t_apdu_container
        self.beacon_name:str                          = beacon_name
        self.bac_l7_driver:tgbv_bac_l7.TgbvBacL7|ops1955_bac_l7.Ops1955BacL7 = get_rse_driver(beacon_name)
        self.rnd_rse_val                              = compute_rnd_rse_from_session_time()
        self.init_data                                = None
        self.last_rs_t_apdu_val:tuple[str, Any]|None   = None
        self.last_vst_val:dict[str, Any]|None         = None
        self.transaction_data_filename                = None
        self.transaction_uuid        = None

    def update_rnd_rse(self):
        self.rnd_rse_val = compute_rnd_rse_from_session_time()

    async def reset_beacon(self):
        rse_dsrc_l7_logger.info('L7: Resetting beacon!!')
        await self.bac_l7_driver._pertel_reset_beacon()

    BeaconModes = typing.Literal['Stopped', 'Transparent', 'Maintenance']
    async def change_trx_mode(self, mode_name:BeaconModes = 'Stopped'):

        if self.bac_l7_driver is None:
            rse_dsrc_l7_logger.error("L7: Beacon not initialized/configured!!")
            return
        rse_dsrc_l7_logger.info(f"Changing beacon mode to '{mode_name}'")

        tgbv_gea_bcm_operating_modes_enum_values = {
            'Stopped': 0x00,
            'Transparent': 0x01,
            'Maintenance': 0x03
        }
        if self.beacon_name == 'TGBV':
            mode_code = tgbv_gea_bcm_operating_modes_enum_values[mode_name]
            await self.bac_l7_driver.set_mode(mode_code=mode_code)

    async def transparent(self):
        await self.change_trx_mode(mode_name='Transparent')
        rse_dsrc_l7_logger.info("L7: Set RSE mode to transparent!")

    async def shutdown_beacon(self):
        if self.bac_l7_driver is None:
            rse_dsrc_l7_logger.error("L7 shutdown error: Beacon not initialized/configured!!")
            return
        await self.bac_l7_driver.set_mode(0x00)

    def get_last_beacon_state(self):
        if self.bac_l7_driver is None:
            rse_dsrc_l7_logger.error("L7: Beacon not initialized/configured!!")
            return

        return pertel_beacon_state_description(self.bac_l7_driver.beacon_state)

    # Start sending a BST
    async def try_to_start_bst_emission_and_await_vst(self, fragmented_t_apdu_with_bst: bytes):
        # Finally start BST emission!!
        if 'bst_timeout_delay' in self.bcm_config['dsrc_l7_config']:
            bst_timeout_delay = self.bcm_config['dsrc_l7_config']['bst_timeout_delay']
            try:
                vst_awaitable = self.bac_l7_driver._pertel_start_bst_emission_and_await_vst(fragmented_t_apdu_with_bst)
                response = await asyncio.wait_for(vst_awaitable, timeout=bst_timeout_delay)
            except TimeoutError as exc:
                rse_dsrc_l7_logger.error('BST response timeout!')
                await self.bac_l7_driver._pertel_stop_bst_emission()
                # raise exc
                raise AbortedInitPhase('BST response timeout!')
        else:
            response = await self.bac_l7_driver._pertel_start_bst_emission_and_await_vst(fragmented_t_apdu_with_bst)

        if response[1] == 2:
            rse_dsrc_l7_logger.critical("A Transaction is unclosed!!")
            raise UnclosedTransactionException("A Transaction is unclosed!!")

        return response

    async def start_bst_emission_and_await_vst(self, bst_value: dict):
        efc_asn_compilation.EfcDsrcGeneric.BST.set_val(bst_value)
        rse_dsrc_l7_logger.debug(f"BST in ASN:\n{efc_asn_compilation.EfcDsrcGeneric.BST.to_asn1()}")
        last_sent_bst:bytes = efc_asn_compilation.EfcDsrcGeneric.BST.to_uper()
        rse_dsrc_l7_logger.debug(f"BST value (UPER hex): {last_sent_bst.hex().upper()}")

        initialization_request_value = ('initialisationRequest', bst_value)

        self.t_apdu_container.set_val(initialization_request_value)
        # bcm_logger.debug(f"T_APDU containing BST in ASN:\n{TApdu_container.to_asn1()}")

        initialization_request_jval = self.t_apdu_container._to_jval()
        last_sent_t_apdu_containing_bst:bytes = self.t_apdu_container.to_uper()
        # bcm_logger.info(f"T_APDU containing BST (UPER hex): {TApdu_container.to_uper().hex().upper()}")
        t_apdu_uper_logger.debug(f'[TX] BST: 0x{last_sent_t_apdu_containing_bst.hex().upper()}')

        fragmented_t_apdu_with_bst = self.frag_header + last_sent_t_apdu_containing_bst
        rse_dsrc_l7_logger.info(f"RSE is now emitting BST and awaiting VST from OBE...")

        try:
            response = await self.try_to_start_bst_emission_and_await_vst(fragmented_t_apdu_with_bst)
        except UnclosedTransactionException:
            rse_dsrc_l7_logger.info('Closing unclosed leftover transaction...')
            await self.send_close_transaction_echo()
            await asyncio.sleep(0.1)
            # raise SystemExit("Unclosed transaction! Exiting...")

            response = await self.try_to_start_bst_emission_and_await_vst(fragmented_t_apdu_with_bst)

        rse_dsrc_l7_logger.debug("We now get the lastest BeaconID just after starting the BST")

        await self.check_and_update_beacon_state()

        return initialization_request_jval

    async def initialize_transaction(
            self,
            manufacturer_id=0x31,
            individual_id=0x111,
            mand_applications=[1, 20, 29],
            profile=0x00,
            profile_list=[0x00],
            non_mand_applications = [],
            timeout_delay:float=0
        ) -> tuple[dict, dict]:
        """
        The initialization phase comprises 2 steps for the beacon:
        Start of a BST, and
        wait for a VST

        The initialization phase locks the transaction thread when a VST is received!
        When the transaction is closed (no longer in progress) the transaction lock is released.
        """

        # Override beaconId value from config, ignoring function arguments!
        if 'beaconId' in self.bcm_config:
            beacon_id = self.bcm_config['beaconId']

            manufacturer_id = beacon_id['manufacturerid']
            individual_id = beacon_id['individualid']

        await self.check_and_update_beacon_state()

        try:
            if self.bac_l7_driver._is_transaction_in_progress():
                rse_dsrc_l7_logger.error("Do not try to initilize a transaction! One is already in progress!")
                # bcm_logger.debug("We lock the thread until the opened transaction is closed!")
                raise BeaconManagerException("Transaction already in progress!!")
        except:
            await self.send_close_transaction_echo()

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
        initialization_request_jval = await self.start_bst_emission_and_await_vst(bst_value=bst_value)

        rse_dsrc_l7_logger.info("A VST was received!")
        fragmented_t_apdu_init_resp_datagram = self.bac_l7_driver.get_vst()
        # bcm_logger.debug(f"Fragmented T_APDU containing VST (UPER hex): {fragmented_t_apdu_init_resp_datagram.hex().upper()}")

        rse_dsrc_l7_logger.debug("We now remove the fragmentation header and instantiate an T_APDU object from the response!")
        t_apdu_init_resp_datagram = bytes(fragmented_t_apdu_init_resp_datagram[1:])
        t_apdu_uper_logger.debug(f"[RX] VST: 0x{t_apdu_init_resp_datagram.hex().upper()}")

        rse_dsrc_l7_logger.debug("We now instantiate a T_APDU object from the UPER response!")
        self.t_apdu_container.from_uper(t_apdu_init_resp_datagram)
        rse_dsrc_l7_logger.debug(f"T_APDU containing VST value: {self.t_apdu_container._val}")
        rse_dsrc_l7_logger.info(f"T_APDU containing VST in ASN:\n{self.t_apdu_container.to_asn1()}")

        # bcm_logger.debug(f"T_APDU containing VST in JER:\n{TApdu_container.to_jer()}")
        last_response_t_apdu_json = self.t_apdu_container._to_jval()
        self.last_rs_t_apdu_val = self.t_apdu_container._val

        # Storing VST in global var
        self.last_vst_val = self.last_rs_t_apdu_val[1]

        self.transaction_data_filename, self.transaction_uuid, self.init_data = disk_transaction_persistence.create_transaction_data_file_from_init_phase_data(initialization_request_jval, last_response_t_apdu_json)

        return (bst_value, self.last_vst_val)

    async def init_and_close_transaction_with_cb(
            self,
            callback:typing.Callable[[dict, dict], typing.Coroutine[None, None, typing.Any]],
            mand_applications=[],
            ):
        bst_value, vst_value = await self.initialize_transaction(mand_applications=mand_applications)
        try:
            result = await callback(bst_value, vst_value)
            rse_dsrc_l7_logger.info('Transaction successful! Closing ...')
            await self.send_close_transaction_echo()
            return result
        except RuntimeError:
            rse_dsrc_l7_logger.error('Error during transaction! Closing...')
            await self.send_close_transaction_echo()

    async def send_req_t_apdu_and_obtain_resp_t_apdu(self, asn1_request_t_apdu_value, close_transaction=False) -> dict:
        if close_transaction:
            rse_dsrc_l7_logger.info(f"Closing Transaction!! Info: BAC L2 command for closing a transaction is 0x06.")

        rse_dsrc_l7_logger.debug(f"Preparing request T-APDU to be sent...")
        self.t_apdu_container.set_val(asn1_request_t_apdu_value)
        rse_dsrc_l7_logger.info(f"Request T-APDU value: {self.t_apdu_container._val}")

        # Needed to store transaction data as JSON!
        request_t_apdu_jval = self.t_apdu_container._to_jval()

        request_t_apdu_uper = self.t_apdu_container.to_uper()
        if request_t_apdu_uper is None:
            raise ValueError("Could not convert T-APDU to UPER!")

        t_apdu_uper_logger.debug(f'[TX] Rq T-APDU: 0x{request_t_apdu_uper.hex().upper()}')

        fragmented_t_apdu_request = self.frag_header + request_t_apdu_uper

        # Sending command!!!
        bac_l2_response = (await self.bac_l7_driver
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
                rse_dsrc_l7_logger.error(f'[BAC L2] Error code (0x{bac_l2_error_code:02X}) present in BAC L2 response!!')
                raise Exception(f'[BAC L2] Error code (0x{bac_l2_error_code:02X}) present in BAC L2 response!!')
        self.bac_l7_driver.last_t_apdu_response_datagram
        fragmented_t_apdu_with_response_bytes = self.bac_l7_driver.last_t_apdu_response_datagram
        rse_dsrc_l7_logger.info(f"Fragmented T-APDU response obtained from beacon in hex (UPER hex): {fragmented_t_apdu_with_response_bytes.hex().upper()}")

        try:
            t_apdu_with_response_bytes = bytes(fragmented_t_apdu_with_response_bytes[1:])
            t_apdu_uper_logger.debug(f'[RX] Rs T-APDU: 0x{t_apdu_with_response_bytes.hex().upper()}')

            t_apdu_response_value = self.decode_t_apdu_response_uper(t_apdu_with_response_bytes)

            self.t_apdu_container.set_val(t_apdu_response_value)
            response_t_apdu_jval = self.t_apdu_container._to_jval()

        except UnclosedTransactionException:
            rse_dsrc_l7_logger.error("Error when decoding T-APDU response!!")
            rse_dsrc_l7_logger.info("Unclosed Transaction Exception: We simply send an ECHO.request to close the transaction...")

            eid = asn1_request_t_apdu_value[1]['eid']
            await self.send_close_transaction_echo(eid=eid)
            return {}

        valid_stamp = self.verify_obe()
        # Storing transaction files T-APDUs locally as a JSON
        disk_transaction_persistence.add_t_apdu_data_to_transaction_data(self.transaction_uuid, self.transaction_data_filename, request_t_apdu_jval, response_t_apdu_jval, valid_stamp)

        return response_t_apdu_jval

    def verify_obe(self):
        if self.last_rs_t_apdu_val is None:
            raise ValueError("Execute decode_t_apdu_response_uper() first, so that self.last_rs_t_apdu_val is defined!")
    
        get_st_act_rs_val = self.last_rs_t_apdu_val[1]
        attr_list_efc_container = efc_asn_compilation.EfcDsrcGeneric.EfcContainer

        if not self.last_vst_val or not get_st_act_rs_val or not self.rnd_rse_val or not attr_list_efc_container:
            return False
        return verify_obe_auth(self.last_vst_val, get_st_act_rs_val, self.rnd_rse_val, attr_list_efc_container)

    async def check_and_update_beacon_state(self):
        if self.beacon_name is None:
            rse_dsrc_l7_logger.critical('No beacon is set!! Please fix the RSE config for a beacon to be initialized properly via BAC L7.')
            raise NoBeaconInitialized('No beacon is set!! Please fix the RSE config for a beacon to be initialized properly via BAC L7.')

        await self.bac_l7_driver._pertel_get_communication_count()

        if self.beacon_name == 'TGBV':
            beacon_state = await self.bac_l7_driver.update_state()
            if not type(self.bac_l7_driver) is tgbv_bac_l7.TgbvBacL7:
                raise RuntimeError("L7: Beacon name is TGBV, but driver is not TGBV!!")

            if beacon_state[1] == pertel_bac_l7.BCM_MODE_Enum.PERTEL_MODE_Stopped:
                raise BeaconManagerException("Beacon is in Stopped mode, not Transparent!!")

            rse_dsrc_l7_logger.debug(f"Last BeaconID: {self.bac_l7_driver.get_beacon_id().hex().upper()}")
            return beacon_state
        elif self.beacon_name == 'OPS1955':
            pass

    def get_init_data(self):
        return self.init_data

    def get_parameter_for_eid(self, eid):
        # Kapsch System Element: EID 0, no VST parameter
        if eid == 0:
            rse_dsrc_l7_logger.info(f'Kapsch System Element has no Parameter in VST!!!')
            return b''
        return self.get_parameter_bytes_from_eid_on_vst_value(eid=eid)

    def decode_t_apdu_response_uper(self, t_apdu_with_response_bytes):
        rse_dsrc_l7_logger.debug(f"Decoding received response T-APDU...")
        try:
            self.t_apdu_container.from_uper(t_apdu_with_response_bytes)
        except pycrate_core.charpy.CharpyErr:
            rse_dsrc_l7_logger.critical(f'[Pycrate UPER decoder] T-APDU response UPER decoding error!! T-APDU UPER hex value: {t_apdu_with_response_bytes.hex().upper()}')
            raise TApduResponseDecodeError('T-APDU response UPER decoding error!!')

        self.last_rs_t_apdu_val = self.t_apdu_container._val
        rse_dsrc_l7_logger.debug(f"Response T-APDU value: {self.last_rs_t_apdu_val}")
        log_attrs_in_get_resp_in_hex_uper_format(self.last_rs_t_apdu_val)

        rse_dsrc_l7_logger.info(f"Response T-APDU in ASN:\n{self.t_apdu_container.to_asn1()}")
        # bcm_logger.debug(f"Response T-APDU decoded with JER:\n{TApdu_container.to_jer()}")
        last_response_t_apdu_json = self.t_apdu_container._to_jval()
        # bcm_logger.debug(f"Response T-APDU in JSON: {last_response_t_apdu_json}")

        rse_dsrc_l7_logger.debug(f"Checking if T-APDU contains a return (ret) value (error code)...")
        try:
            return_code = self.last_rs_t_apdu_val[1]["ret"]
            if return_code == 0:
                rse_dsrc_l7_logger.info(f"Return code is present and is 0! (No errors)")
                rse_dsrc_l7_logger.debug(f"ReturnStatus ASN1 decoding:\n{efc_asn_compilation.EfcDsrcGeneric.ReturnStatus.to_asn1()}")
            else:
                rse_dsrc_l7_logger.error(f"Error code present! Return Code: {return_code}")
                efc_asn_compilation.EfcDsrcGeneric.ReturnStatus.set_val(return_code)
                rse_dsrc_l7_logger.error(f"ReturnStatus ASN1 decoding:\n{efc_asn_compilation.EfcDsrcGeneric.ReturnStatus.to_asn1()}")
                # if return_code == 1:
                #     raise TApduResponseException(f"Return Status: {efc_asn_compilation.EfcDsrcGeneric.ReturnStatus.to_asn1()}")
        except KeyError:
            rse_dsrc_l7_logger.info(f"No return code in T-APDU! (No errors)")
        return self.last_rs_t_apdu_val

    def decode_vst_parameter_with_eid_only(self, eid):
        rse_dsrc_l7_logger.debug(f"Decoding VST parameter with EID {eid}...")
        parameter_bytes = self.get_parameter_for_eid(eid)

        decoded_parameter = custom_its_per_decoders.decode_vst_parameter_oct_str_bytes(parameter_bytes)
        return decoded_parameter

    def get_parameter_bytes_from_eid_on_vst_value(self, eid:int, vst_value=None) -> bytes:
        if not vst_value:
            if not self.last_vst_val:
                raise ValueError('Undefined VST value!')
            vst_value = self.last_vst_val
        return custom_its_per_decoders.get_parameter_bytes_from_vst_value_on_eid(eid, vst_value)

    def get_obu_contract_ref_with_eid_only(self, eid:int, vst_value:dict|None=None):
        if not vst_value:
            if not self.last_vst_val:
                raise ValueError('Undefined VST value!')
            vst_value = self.last_vst_val
        return custom_its_per_decoders.get_obu_contract_ref_from_vst_value(eid, vst_value)

    def compute_access_credentials_for_eid(self, eid:int) -> bytes:
        rse_dsrc_l7_logger.debug(f"Computing Access Credentials for EID {eid}...")
        decoded_vst_param = self.decode_vst_parameter_with_eid_only(eid)

        if len(decoded_vst_param) == 1:
            # VST parameter contains EFC-CM only, no AC_CR-KeyRef or RndOBE present
            # As such, we do not need any access credentials!
            return bytes(4)
        ac_cr_key_ref = decoded_vst_param['AC_CR-KeyReference']
        rnd_obe = decoded_vst_param['RndOBE']
        obu_contract_ref = self.get_obu_contract_ref_with_eid_only(eid)

        td_name = tc_manage_toll_domains.get_current_toll_domain()
        access_credentials_int = tc_dsrc_auth.compute_access_credentials_for_obu_on_td(obu_contract_ref, rnd_obe, ac_cr_key_ref, td_name=td_name)
        access_credentials_bytes = access_credentials_int.to_bytes(4, 'big')
        return access_credentials_bytes
        # except dsrc_security.TollDomainException:
        #     bcm_logger.error("TollDomainException occurred!", stack_info=True)

    async def send_get_request(self, eid, accessCredentialsPresent:bool = False, attrIdList=None, close_transaction = False) -> dict:
        if accessCredentialsPresent:
            accessCredentials = self.compute_access_credentials_for_eid(eid)
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
        rse_dsrc_l7_logger.debug(f"Get.Request value: {efc_asn_compilation.EfcDsrcGeneric.Get_Request._val}")

        t_apdu_with_get_request_value = ('getRequest', get_req_value)
        response_t_apdu_value = await self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_get_request_value, close_transaction=close_transaction)

        rse_dsrc_l7_logger.debug("We now obtain the GET.response object from the T_APDU response!")
        rse_dsrc_l7_logger.debug("GET.response is a parameterized type, so we cannot encode/decode it, only the T_APDU!")

        return response_t_apdu_value

    # SET.request only exists for EFC, LAC UNI (AIDs 1, 20 and 29)! Not for CCC (AID 20).
    async def send_set_request(self, eid, access_credentials:int, attrList, close_transaction=False):
        aid = 1
        # SET.Request is filled with 1 bit valued at 0
        set_req_value = {
            'fill': (0, 1),
            'eid': eid,
            'mode': True,
            'accessCredentials': access_credentials,
            'attrList': attrList
        }

        rse_dsrc_l7_logger.debug(f"SET.Request value: {set_req_value}")

        t_apdu_with_set_request_value = ('set-request', set_req_value)

        prev = self.t_apdu_container
        self.t_apdu_container = efc_asn_compilation.EfcDsrcGeneric.T_APDUs
        response_t_apdu_value = await self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_set_request_value, close_transaction=close_transaction)
        if self.t_apdu_container._val is None:
            raise ValueError("Could not set T-APDU ")
        rse_dsrc_l7_logger.debug(f"SET.Response value: {self.t_apdu_container._val[1]}")
        self.t_apdu_container = prev

        return response_t_apdu_value

    async def send_set_request_with_eack_ac_cr(self, eid, attrList, close_transaction=False):
        accessCredentials = self.compute_access_credentials_for_eid(eid)
        # Get.Request is filled with 1 bit valued at 0
        set_req_value = {
            'eid': eid,
            'accessCredentials': accessCredentials,
            'attrList': attrList,
            'fill': (0, 1)
        }

        efc_asn_compilation.EfcDsrcGeneric.Set_Request.set_val(set_req_value)
        rse_dsrc_l7_logger.debug(f"SET.Request value: {efc_asn_compilation.EfcDsrcGeneric.Set_Request._val}")

        t_apdu_with_set_request_value = ('setRequest', set_req_value)

        prev = self.t_apdu_container
        self.t_apdu_container = efc_asn_compilation.EfcDsrcGeneric.T_APDUs
        response_t_apdu_value = await self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_set_request_value, close_transaction=close_transaction)
        if self.t_apdu_container._val is None:
            raise ValueError("Could not set T-APDU ")
        rse_dsrc_l7_logger.debug(f"SET.Response value: {self.t_apdu_container._val[1]}")
        self.t_apdu_container = prev

        return response_t_apdu_value

    async def send_action_request(
            self,
            mode=True,
            eid=0,
            actionType=0xA,
            accessCredentialsPresent:bool = True,
            actionParameter = None,
            iid = None,
            close_transaction = False):
        if accessCredentialsPresent:
            accessCredentials = self.compute_access_credentials_for_eid(eid)
        else:
            accessCredentials = None
        if not actionParameter:
            actionParameter = ('setmmirq', 0)
        rse_dsrc_l7_logger.info(f"Preparing an ACTION.request with ActionType ({actionParameter[0]})")

        # ACTION.request has a parameter, which needs to be inside a container
        efc_asn_compilation.EfcDsrcGeneric.EfcContainer.set_val(actionParameter)
        parameter_tag = efc_asn_compilation.EfcDsrcGeneric.EfcContainer._tag

        rse_dsrc_l7_logger.debug(f"ActionParameter is an EfcContainer of Type ({actionParameter[0]}) (tag {parameter_tag}) value decoded with JER:\n{efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_jer()}")
        rse_dsrc_l7_logger.debug(f"Same value but APER-encoded in hex: {efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_aper().hex().upper()}")

        action_request_value = {
            'mode': mode,
            'eid': eid,
            'actionType': actionType,
            'accessCredentials': accessCredentials,
            'actionParameter': actionParameter,
            'iid': iid
            }
        rse_dsrc_l7_logger.debug(f"ACTION.request value: {action_request_value}")

        # Ignore keys in dict that map to None!!
        # That is, remove OPTIONAL elements that map to None
        # This is specially the case for the OPTIONAL accessCredentials and iid
        action_request_value = {key: value for key, value in action_request_value.items() if value is not None}

        t_apdu_with_action_req_value = ('actionRequest', action_request_value)
        rse_dsrc_l7_logger.debug(f"T-APDU with ACTION.request value: {t_apdu_with_action_req_value}")

        self.t_apdu_container.set_val(t_apdu_with_action_req_value)
        rse_dsrc_l7_logger.info(f"T-APDU with ACTION.request in ASN:\n{self.t_apdu_container.to_asn1()}")
        rse_dsrc_l7_logger.debug(f"ACTION.request with ActionType {actionType} and actionParameter of type {actionParameter[0]} being now sent...")

        response_t_apdu_value = await self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_action_req_value, close_transaction)
        return response_t_apdu_value

    async def presentation_request(
            self,
            eid:int,
            accessCredentialsPresent:bool = True,
            attrIdList=[],
            operator_auk_ref=111,
            close_transaction=False):
        return await self.send_get_stamped_request(eid, accessCredentialsPresent, attrIdList, operator_auk_ref, close_transaction)

    async def send_get_stamped_request(
            self,
            eid:int,
            accessCredentialsPresent:bool = True,
            attrIdList=[],
            operator_auk_ref=111,
            close_transaction=False):
        rse_dsrc_l7_logger.debug("Preparing an ActionParameter for an Action-Request of type GET_STAMPED.request (Presentation request)...")
        get_stamped_rq_value = self.get_stamped_request_action_parameter_preparation(eid, attrIdList, operator_auk_ref)

        rse_dsrc_l7_logger.debug("Putting the GetStampedRq inside a 'gstrq' EFC Container...")
        container_with_get_stamped_rq_value = ('gstrq', get_stamped_rq_value)
        rse_dsrc_l7_logger.debug(f"Container with GetStampedRq value: {container_with_get_stamped_rq_value}")

        # ActionType is 0 for GET_STAMPED.request and Mode is True (Always expects a response)
        response_t_apdu_value = await self.send_action_request(True, eid, 0, accessCredentialsPresent, container_with_get_stamped_rq_value, close_transaction=close_transaction)

        # custom_its_per_decoders.decode_get_response_param(response_t_apdu_value)

        return response_t_apdu_value

    def get_stamped_request_action_parameter_preparation(self, eid:int, attrIdList:list = [], operator_auk_ref=111):
        """
        ACTION.request of type GET_STAMPED.request (ActionType=0).

        The ActionParameter is thus of type GetStampedRs
        """
        if not attrIdList:
            attrIdList = []

        rse_dsrc_l7_logger.debug(f"Preparing a GET_STAMPED.request to get attributes with ids {attrIdList}")
        self.update_rnd_rse()

        get_stamped_rq_value = {
            'attributeIdList': attrIdList,
            'nonce': self.rnd_rse_val,
            'keyRef': operator_auk_ref
            }
        rse_dsrc_l7_logger.debug(f"GetStampedRq value to be stored in definition: {get_stamped_rq_value}")
        efc_asn_compilation.EfcDsrcApplication.GetStampedRq.set_val(get_stamped_rq_value)

        rse_dsrc_l7_logger.debug(f"GetStampedRq in ASN: {efc_asn_compilation.EfcDsrcApplication.GetStampedRq.to_asn1()}")
        # bcm_logger.info(f"GetStampedRs in JER:\n{efc_asn_compilation.EfcDsrcApplication.GetStampedRq.to_jer()}")
        return get_stamped_rq_value

    async def send_echo_action_request(self, eid=0, text='Hello, World!', close_transaction=False):
        """EID should always be 0 for ECHO.request!!!"""
        rse_dsrc_l7_logger.debug(f"Preparing an ECHO.request")

        echo_rq_value = ('octetstring', text.encode('utf-8'))

        efc_asn_compilation.EfcDsrcGeneric.EfcContainer.set_val(echo_rq_value)
        rse_dsrc_l7_logger.debug(f"EfcContainer of Type 02 (OCTET STRING) value decoded with JER:\n{efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_jer()}")
        rse_dsrc_l7_logger.debug(f"EfcContainer of Type 69 (OCTET STRING) value decoded with PER: {efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_uper()}")

        # ActionType is 15 or 0xF for ECHO.request
        echo_action_request_val = {
            'mode': True,
            'eid': 0,
            'actionType': 0xF,
            'actionParameter': echo_rq_value
            }
        t_apdu_with_echo_action_req_value = ('actionRequest', echo_action_request_val)
        rse_dsrc_l7_logger.info(f"ACTION.request of Type 15 (ECHO) being now sent...")

        response_t_apdu_json = await self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_echo_action_req_value, close_transaction=close_transaction)
        # response_t_apdu_json = send_action_request(mode=True, eid=eid, actionType=15, accessCredentialsPresent=False, actionParameter=echo_rq_value, close_transaction=close_transaction)
        return response_t_apdu_json

    async def set_mmi(self, eid=0, close_transaction=False):
        rse_dsrc_l7_logger.debug(f"Preparing a SET_MMI.request")
        rse_dsrc_l7_logger.debug(f"The function to send ACTION.requests is defined to send a SET_MMI by default if no arguments are provided!")

        set_mmi_request_value = 0
        # SetMMI is a parameterized type, so it needs to be inside a container
        set_mmi_efc_container_value = ('setmmirq', set_mmi_request_value)
        efc_asn_compilation.EfcDsrcGeneric.EfcContainer.set_val(set_mmi_efc_container_value)
        rse_dsrc_l7_logger.debug(f"EfcContainer of Type 69 (SET_MMI) value decoded with JER:\n{efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_jer()}")
        rse_dsrc_l7_logger.debug(f"EfcContainer of Type 69 (SET_MMI) value decoded with PER: {efc_asn_compilation.EfcDsrcGeneric.EfcContainer.to_uper()}")

        # SetMMI ActionType is 0xA, or 10 in decimal
        set_mmi_action_request_val = {
            'mode': True,
            'eid': eid,
            'actionType': 0xA,
            'actionParameter': set_mmi_efc_container_value
            }

        t_apdu_with_set_mmi_action_req_value = ('actionRequest', set_mmi_action_request_val)
        rse_dsrc_l7_logger.info(f"ACTION.request of Type 10 (SET_MMI) being now sent...")

        t_apdu_with_action_response = await self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_set_mmi_action_req_value, close_transaction)
        return t_apdu_with_action_response

    async def send_close_transaction_echo(self, eid=0, text="Hello, World!"):
        try:
            return await self.send_echo_action_request(eid=eid, text=text, close_transaction=True)
        except ObuResponseTimeout as exc:
            rse_dsrc_l7_logger.error('OBU response timeout during SET_MMI request!')
            # We optionally ignore OBU response timeouts during SET_MMI requests!
            if not self.bcm_config['bac_l2_config']['IGNORE_OBU_TIMEOUTS_WHEN_CLOSING_TRANSACTION']:
                raise exc

    async def send_close_transaction_setmmi(self, eid=0):
        try:
            return await self.set_mmi(eid, close_transaction=True)
        except ObuResponseTimeout as exc:
            rse_dsrc_l7_logger.error('OBU response timeout during SET_MMI request!')
            # We optionally ignore OBU response timeouts during SET_MMI requests!
            if not self.bcm_config['bac_l2_config']['IGNORE_OBU_TIMEOUTS_WHEN_CLOSING_TRANSACTION']:
                raise exc

    async def send_close_transaction_setmmi_if_transaction_open(self, eid=0):
        if self.bac_l7_driver._is_transaction_in_progress():
            return
        return await self.send_close_transaction_setmmi(eid)

# RSE <> OBE = Host <> Host BAC L2 <> Beacon BAC L2 <> Beacon DSRC L7 <> OBE DSRC L7
def build_rse_app(beacon_name:str, aid=20):
    """Initialize the beacon manager wrapper"""
    # PDU cannot be 0 or 1
    pdu = 0x02
    if aid == 1:
        t_apdu_container = efc_asn_compilation.EfcDsrcGeneric.EfcContainer
    elif aid == 20:
        t_apdu_container = efc_asn_compilation.EfcCcc.CccTApdus

    rse_app = RseDsrcL7App(pdu, beacon_name, t_apdu_container)
    rse_dsrc_l7_logger.info("Initialized RSE DSRC L7 app!!")
    return rse_app

def build_and_init_rse_app(beacon_name:str, aid=20):
    rse_dsrc_l7_logger.debug("Instantiating/Initializing BeaconManager class...")
    rse_app = build_rse_app(beacon_name, aid)
    rse_dsrc_l7_logger.info("Initialized RSE DSRC L7 app!!")

    # SETTING BEACON TO TRANSPARENT MODE!!
    asyncio.run(rse_app.transparent())
    return rse_app
