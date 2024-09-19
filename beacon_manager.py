import ctypes
from ctypes import POINTER, wintypes, c_void_p, c_char_p, c_uint, c_int, c_byte, c_bool, c_ulong, c_ushort
from ctypes.wintypes import HWND, LPCWSTR, UINT, BYTE, WORD, DWORD, CHAR, BOOL, LPBYTE

import json
import threading
import logging

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from gea_bcm_dll_loader import *
import custom_ITS_per_decoders

with open('settings/beacon_config.json', 'r') as beacon_settings_file:
    beacon_settings = json.load(beacon_settings_file)

bcm_logger = logging.getLogger(__name__)

def bcm_error_handler(bcm_error: BCMError):
    if not isinstance(bcm_error, int):
        raise TypeError(bcm_error)
    if bcm_error != BCM_ERR_Enum.BCM_NoError:
        bcm_logger.error(f"Beacon Manager Error {bcm_error}: {BCMError.get_error_description(bcm_error)}")

        # Handle error case if needed
        if bcm_error == BCM_ERR_Enum.BCM_TrxInProgress:
            bcm_logger.error(f"Cannot execute function because a transaction is in progress!")

        bcm_logger.error(f"Beacon Manager Error {bcm_error}: {BCMError.get_error_description(bcm_error)}")

def cb_error_handler(callback_code, error_code):
    if callback_code == BCM_CALLBACK_Enum.BCM_CB_ERR:
        bcm_logger.error(BCM_Callback.get_description(callback_code))
        # No Exception/Error is raised on callbacks.
        # We only log them
        bcm_logger.error(f"Callback Error ({callback_code}), with BCM error code {error_code}")
        bcm_error_handler(error_code)

# Defining the BeaconManager class
class BeaconManager:
    def __init__(self, serial_port=None, beacon_alarm_state_polling_ms=1000, external_callback:callable = None, external_alarm:callable = None):
        self.beacon_state_ok_trigger = threading.Event()
        self.no_transaction_in_progress = threading.Event()
        self.callback_received_notifier = threading.Condition()
        self.transaction_lock = threading.Lock()
        self.transaction_in_progress = False

        self.external_callback = external_callback
        self.external_alarm = external_alarm

        # This is the BCM structure pointer. It is managed by the DLL
        self.reg_ptr = ST_BCM_REG_PTR()
        # This is the BCM state pointer. It is managed by the DLL
        self.beacon_state = ST_BCM_STATE()
        # Last received VST
        self.last_vst = bytes()
        self.last_vst_obj = {}
        
        # PDU cannot be 0 or 1
        pdu = 0x2
        # PDU is at most 4 bits
        pdu &= 0xF
        # The fragmentation header is 0b1xxxx001, where xxxx is the PDU
        self.frag_header = 0x81 | (pdu << 3)
        
        self.c_callback = BCM_CB_HANDLER(self.bcm_callback)
        self.c_alarm = BCM_ALARM_HANDLER(self.bcm_alarm)
        
        bcm_logger.debug("Initializing GEA BCM...")
        
        send_event_polling_OK = False
        if beacon_alarm_state_polling_ms > 0:
            send_event_polling_OK = True
        # The user registration number is not used internally by the BCM DLL
        # It is thus free for use in our application
        user_registration = 7
        user_params = None
        if beacon_settings["communication_mode"] == "serial":
            if serial_port is None:
                serial_port = beacon_settings["serial_config"]["beacon_serial_port"]
            serial_port_speed = BaudRate_Enum.BCM_CFG_115200
            result = bcm_init_manager_fnc(
                ctypes.byref(self.reg_ptr),
                user_registration,
                user_params,
                serial_port,
                serial_port_speed,
                BCM_STATION_Enum.BCM_Secondary,
                beacon_alarm_state_polling_ms,
                send_event_polling_OK,
                self.c_callback,
                self.c_alarm
            )
        else:
            beacon_ip_address_bytes = beacon_settings["tcp_ip_config"]["ip_address"].encode('utf-8')
            beacon_tcp_port = beacon_settings["tcp_ip_config"]["tcp_port"]

            result = bcm_init_manager_fnc_ip(
                ctypes.byref(self.reg_ptr),
                user_registration,
                user_params,
                beacon_ip_address_bytes,
                beacon_tcp_port,
                BCM_STATION_Enum.BCM_Secondary,
                beacon_alarm_state_polling_ms,
                send_event_polling_OK,
                self.c_callback,
                self.c_alarm
            )

        bcm_error_handler(result)
        self.update_beacon_id()
        self.handle_init_errors()
    def update_beacon_id(self):
        bcm_logger.debug("Getting Beacon ID...")
        
        beacon_id_buffer_array = ctypes.create_string_buffer(BCM_FIXED_SIZES_Enum.BCM_SIZE_BEACONID)

        # Pointer where the BeaconID will be stored by BCM
        lp_beacon_id = ctypes.cast(beacon_id_buffer_array, POINTER(BYTE))

        bcm_get_beacon_id(self.reg_ptr, lp_beacon_id)
        self.last_beacon_id = bytes(beacon_id_buffer_array[0:BCM_FIXED_SIZES_Enum.BCM_SIZE_BEACONID])

        bcm_logger.debug(f"Latest Beacon ID in hex: {self.last_beacon_id.hex().upper()}")
        return self.last_beacon_id
    
    # Defining the Callback and Alarm default functions (they are both callback functions)
    # But alarm has a state
    # As those callback functions are directly called by the internal thread which is
    # managing the communication with the beacon they should return as
    # quickly as possible
    def bcm_callback(self, reg_ptr, callback_type, error_code):
        bcm_logger.debug("CB: Callback notification received!")
        if callable(self.external_callback):
            bcm_logger.debug("CB: External callback function present! (from the frontend, for exemple)")
            bcm_logger.debug("CB: We now call/notify it!")
            self.external_callback(callback_type, error_code)

        try:
            cb_error_handler(callback_type, error_code)
            bcm_error_handler(error_code)
            bcm_logger.debug("CB: OK! No error occurred in callback: This means a VST was received!")
            bcm_logger.debug("CB: We thus notify all threads waiting on the callback_received_notifier condition")
            with self.callback_received_notifier:
                self.callback_received_notifier.notify_all()
        except:
            bcm_logger.error(f"CB: Error, with BCM error code {error_code}")
            return
    def bcm_alarm(self, reg_ptr, alarm_type, alarm_state):
        bcm_logger.debug(f"AL: Alarm notification ({alarm_type}) received!")
        if callable(self.external_alarm):
            bcm_logger.debug("AL: External alarm function present! (from the frontend, for exemple)")
            bcm_logger.debug("AL: We now call/notify it!")
            self.external_alarm(alarm_type, alarm_state)

        if alarm_type == BCM_ALARMS_Enum.BCM_AlarmPeriph or alarm_type == BCM_ALARMS_Enum.BCM_AlarmBeacon:
            bcm_logger.error(f"Error in Alarm! Description: {BCM_Alarm.get_description(alarm_type)}")
            return
        bcm_logger.debug(f"Alarm description: {BCM_Alarm.get_description(alarm_type)}")
        if alarm_type == BCM_ALARMS_Enum.BCM_EventPollingOK:
            self.beacon_state_ok_trigger.set()
        return
    def handle_init_errors(self):
        """This function handles initialization issues, like:
            Unclosed transactions
            Beacon not in stopped mode
            etc."""

        bcm_logger.debug("Trying get the updated beacon's state...")
        result = self.update_state()

        bcm_logger.debug(f"Beacon State iterator keys: {list(iter(self.beacon_state))}")
        bcm_logger.debug(self.beacon_state)

        if result == BCM_ERR_Enum.BCM_NoError:
            pass
        elif result == BCM_ERR_Enum.BCM_SocketNotConnected:
            bcm_logger.error("Wait for socket to connect before sending commands!")
        else:
            bcm_logger.error("We could not handle the error, so it will be raised")
            bcm_error_handler(result)
        
        self.wait_until_ok()

        bcm_logger.debug("Updating beacon state (It should now be OK)...")
        result = self.update_state()

        # If a previous transaction was not closed, we forcefully reset the beacon
        if self.beacon_state.trxInProgress:
            bcm_logger.error("Previously unclosed transaction in progress!")
            bcm_logger.info("We will forcefully reset the beacon...")
            self.reset_manager()
            
            self.wait_until_ok()

        if self.beacon_state.mode != BCM_MODE_Enum.BCM_MOD_Stopped:
            self.change_mode(BCM_MODE_Enum.BCM_MOD_Stopped)
            bcm_logger.debug("Changed operating mode to stopped!")
        self.update_state()
        return self.beacon_state

    def wait_until_ok(self):
        bcm_logger.debug("Polling the beacon state until it is in an OK state...")
        self.beacon_state_ok_trigger.wait()
        bcm_logger.debug("Beacon is OK!!!")

    def display_cb_event_trigger(self):
        bcm_logger.debug("\tWaiting for CB notification...")
        with self.callback_received_notifier:
            self.callback_received_notifier.wait()
        bcm_logger.debug("\tCB notification received!!! You can receive a VST now.")
        
    def update_state(self):
        bcm_logger.debug(f"Udpating beacon state...")
        if self.beacon_state.trxInProgress:
            bcm_logger.error(f"Do not try to update the state: A transaction is in progress! Otherwise, an Exception will be raised.")
            return
        
        result = bcm_check_state(self.reg_ptr, ctypes.byref(self.beacon_state))
        bcm_error_handler(result)

        bcm_logger.debug(f"Beacon state: {self.beacon_state}")
        return result
    def get_last_beacon_state(self):
        bcm_logger.debug(f"Beacon state dict: {dict(self.beacon_state)}")
        # return vars(self.beacon_state)
        return dict(self.beacon_state)
    
    def get_config(self):
        bcm_config = ST_BCM_CONFIG()
        
        result = bcm_get_config(self.reg_ptr, ctypes.byref(bcm_config))
        bcm_error_handler(result)

        return bcm_config
    
    def change_mode(self, operating_mode_code):
        result = bcm_change_mode(self.reg_ptr, operating_mode_code)
        bcm_error_handler(result)
    def shutdown(self):
        result = bcm_close_manager(ctypes.byref(self.reg_ptr))
        bcm_error_handler(result)
        
    def reset_manager(self):
        result = bcm_reset(self.reg_ptr)
        bcm_error_handler(result)
    
    def initialization(self, manufacturer_id=0x31, individual_id=0x111, mandapplications=[1, 20, 29], profile=0x00, profile_list=[0x00], non_mand_applications = [], bst_type:int = BCM_BST_TYPE_Enum.BCM_BST_ChangeBID):
        if self.beacon_state.trxInProgress:
            bcm_logger.error("Do not try to initilize a transaction! One is already in progress!")
            return
        bcm_logger.debug("We lock the thread until the opened transaction is closed!")
        #self.no_transaction_in_progress.wait()
        #self.no_transaction_in_progress.clear()

        self.start_bst(manufacturer_id, individual_id, mandapplications, profile, profile_list, non_mand_applications, bst_type)
        bcm_logger.debug("No errors occurred when starting BST!")
        
        bcm_logger.info("We now wait on the main thread until we a VST notification is received...")
        self.wait_for_vst_notification()
        #self.no_transaction_in_progress.set()

        bcm_logger.debug("A VST notification was received! We now get the VST")
        vst_datagram = self.get_vst()
        bcm_logger.debug("We now instantiate a VST object from the response")
        # Decoding VST
        self.last_vst_obj = custom_ITS_per_decoders.VST(vst_datagram)

        bcm_logger.debug(f'Decoded VST: {self.last_vst_obj}')
        return self.last_vst_obj

    # Start sending a BST
    def start_bst(self, manufacturer_id=0x31, individual_id=0x111, mandapplications=[1, 20, 29], profile=0x00, profile_list=[0x00], non_mand_applications = [], bst_type:int = BCM_BST_TYPE_Enum.BCM_BST_ChangeBID):
        bst_datagram = custom_ITS_per_decoders.encode_bst_datagram(self.frag_header, manufacturer_id, individual_id, mandapplications, profile, profile_list, non_mand_applications)
        if len(bst_datagram) > BCM_SIZEMAX_Enum.BCM_SIZEMAX_BST:
            bcm_logger.error(f"Datagram is too big! Will probably cause a BST error")
        result = self.start_bst_wrapper(bytes(bst_datagram), bst_type)

        bcm_logger.debug("We now get the lastest BeaconID just after starting the BST")
        self.update_beacon_id()
        bcm_logger.debug(f"Last BeaconID: {self.last_beacon_id.hex().upper()}")

        return result
        
    def start_bst_wrapper(self, bst_datagram:bytes, bst_type:int):
        bst_datagram_buffer = ctypes.create_string_buffer(bst_datagram, size=len(bst_datagram))
        # Pointer to the buffered BST datagram
        lp_bst_datagram = ctypes.cast(bst_datagram_buffer, POINTER(BYTE))
        byte_bst_type = BYTE(bst_type)
        bcm_logger.info(f"BST to be sent in hex format: {bst_datagram.hex().upper()}")
        bcm_logger.info(f"Decoded BST: {bst_datagram.hex().upper()}")

        result = bcm_start_bst(self.reg_ptr,
                               lp_bst_datagram,
                               DWORD(len(bst_datagram)),
                               byte_bst_type)
        bcm_error_handler(result)
        bcm_logger.debug("No errors occurred: BST started!")
        st_bcm_reg_ptr_value = ctypes.cast(self.reg_ptr, ctypes.c_void_p).value
        #bcm_logger.debug(f"ST_BCM_REG (dereferenced value): {st_bcm_reg_ptr_value}")
        return result
        
    
    # Wait for the application to be notified through a callback
    def wait_for_vst_notification(self):
        with self.callback_received_notifier:
            self.callback_received_notifier.wait()

    # Wait for a notification then get the VST
    def wait_and_get_vst(self):
        self.wait_for_vst_notification()
        return self.get_vst()
    
    # Get the VST
    # This function should only be called inside the callback declared to the
    # BCM Init Manager
    def get_vst(self):
        bcm_logger.debug("Getting VST...")
        
        dword_max_size = DWORD(BCM_SIZEMAX_Enum.BCM_SIZEMAX_ANSWER)
        vst_answer_buffer_array = ctypes.create_string_buffer(BCM_SIZEMAX_Enum.BCM_SIZEMAX_ANSWER)
        vst_answer_size = DWORD()

        # Pointer where the VST datagram answer will be stored by BCM
        lp_vst_response_datagram = ctypes.cast(vst_answer_buffer_array, POINTER(BYTE))
        
        result = bcm_get_vst(self.reg_ptr,
                             lp_vst_response_datagram,
                             ctypes.byref(vst_answer_size),
                             dword_max_size
                             )
        
        bcm_logger.debug("Handling errors...")
        bcm_error_handler(result)
        bcm_logger.debug("VST received!")

        # Slicing a ctypes array or pointer will automatically produce a Python list
        # We slice it at the given size, not the buffer's maximum size
        received_vst_list = lp_vst_response_datagram[:vst_answer_size.value]

        # Converting VST to bytes structure and storing it in last_vst attribute
        self.last_vst = bytes(received_vst_list)

        # Log the VST
        bcm_logger.info(f"Received VST in hex format: {self.last_vst.hex().upper()}")
        return self.last_vst
    
    def send_command(self, datagram: bytes, close=False):
        lp_cmd_datagram = ctypes.cast(datagram, POINTER(BYTE))
        
        # Buffers and pointers for command response datagrams
        cmd_response_buffer_array = ctypes.create_string_buffer(BCM_SIZEMAX_Enum.BCM_SIZEMAX_CMD)
        dword_cmd_resonse_max_size = DWORD(BCM_SIZEMAX_Enum.BCM_SIZEMAX_CMD)
        lp_cmd_response_datagram = ctypes.cast(cmd_response_buffer_array, POINTER(BYTE))
        cmd_response_size = DWORD()

        bcm_logger.debug(f"Command to be sent in hex format: {datagram.hex().upper()}")

        result = bcm_send_cmd(
            self.reg_ptr,
            lp_cmd_datagram,
            DWORD(len(datagram)),
            lp_cmd_response_datagram,
            ctypes.byref(cmd_response_size),
            dword_cmd_resonse_max_size,
            close
            )
        self.last_cmd_req = bytes(datagram)
        bcm_error_handler(result)

        # Iterating cmd response pointer to get its value/contents
        response_as_list = lp_cmd_response_datagram[:cmd_response_size.value]
        self.last_cmd_response = bytes(response_as_list)
        bcm_logger.debug(f"Command response in hex format: {self.last_cmd_response.hex().upper()}")
        return self.last_cmd_response
    
    def send_get_request(self, eid, access_credentials=None, attribute_ids=None, close = False):
        datagram = custom_ITS_per_decoders.encode_get_request_datagram(self.frag_header, eid, access_credentials, attribute_ids, close)
        return self.send_command(datagram)

    def presentation_request(self, eid:int, access_credentials:int, attribute_ids=[], operator_auk_ref=111, response_expected=True, close=False):
        return self.send_get_stamped_request(eid, access_credentials, attribute_ids, operator_auk_ref, response_expected, close)
    def send_get_stamped_request(self, eid:int, access_credentials:int, attribute_ids=[], operator_auk_ref=111, response_expected=True, close=False):
        datagram = self.get_stamped_request_datagram_preparation(eid, access_credentials, attribute_ids, operator_auk_ref, response_expected, close)
        return self.send_command(datagram)
    def get_stamped_request_datagram_preparation(self, eid:int, access_credentials:int, attribute_ids=[], operator_auk_ref=111, response_expected=True, close = False):
        bcm_logger.debug(f"Preparing a GET_STAMPED.request to get attributes with ids {attribute_ids}")
        action_req_header = 0

        # The ActionParameter is always present in a GET_STAMPED request
        # Also, its container type/choice is set to 17 = 0x11 for a GetStampedRq
        action_req_header = action_req_header | 0b0100
        GetStampedRq_action_type = 0x11

        if response_expected:
            action_req_header = action_req_header | 1

        if access_credentials is not None:
            # Access Credentials is present!
            action_req_header = action_req_header | 0b1000
            # Length + Value
            ac_cr_list = [4] + list(access_credentials.to_bytes(4, 'big'))
        else:
            ac_cr_list = []

        # ActionParamater is always present, so AttributeIdList must be present even if just an empty list (thus with length = 0)
        if attribute_ids is None:
            attribute_ids = []
        if attribute_ids:
            # AttributeIdList is present!
            # Length + Value
            attribute_id_list = [len(attribute_ids)] + attribute_ids
        #else:
        #    attribute_id_list = [00]
        
        # ActionType is a GET_STAMPED
        action_type = 0
        # Attribute 0x20 = 32 is the PAN, or PaymentMeans
        # So the AttributeIdList is set by default to [0x20]

        self.rnd_rse = custom_ITS_per_decoders.encode_date_and_time()
        rnd_rse_list = [4] + list(self.rnd_rse.to_bytes(4, 'big'))
        presentation_request = [self.frag_header, action_req_header, eid, action_type] + ac_cr_list  + [GetStampedRq_action_type] + attribute_id_list + rnd_rse_list + [operator_auk_ref]
        
        bcm_logger.debug(f"Presentation request: {presentation_request}")
        
        # Converting command request to bytes structure and returning it
        return bytes(presentation_request)

    def set_mmi(self, close = False):
        bcm_logger.debug(f"Preparing a SET_MMI.request")
        # SetMMI ActionType is 0xA, or 10 in decimal
        set_mmi_request = [self.frag_header, 0x05, 0x00, 0x0A, 0x00, 0x00]
        set_mmi_datagram = bytes(set_mmi_request)
        self.send_command(set_mmi_datagram, close)
    def decode_last_get_response(self):
        decoded_response = custom_ITS_per_decoders.decode_response(self.last_cmd_response)
        if decoded_response is None:
            return
        try:
            return_status = decoded_response["ReturnStatus"]
            raise(return_status)
        except custom_ITS_per_decoders.ReturnStatus:
            bcm_logger.error(return_status.message)
        decoded_response

    def send_close_transaction_to_obu(self):
        command_response = self.set_mmi(True)
        self.no_transaction_in_progress.clear()
        return command_response
    def stopping(self):
        bcm_logger.info(f"Stopping Beacon Manager!")
        # If a transaction is still open, we close it
        if self.beacon_state.trxInProgress:
            bcm_logger.info(f"A transaction was in progress according to the DLL! Closing it...")
            self.send_close_transaction_to_obu()
        
        self.update_state()

        if self.beacon_state.mode != BCM_MODE_Enum.BCM_MOD_Stopped:
            self.change_mode(BCM_MODE_Enum.BCM_MOD_Stopped)
            bcm_logger.debug("Changed mode to stopped!")