import ctypes
from ctypes import POINTER, wintypes, c_void_p, c_char_p, c_uint, c_int, c_byte, c_bool, c_ulong, c_ushort
from ctypes.wintypes import HWND, LPCWSTR, UINT, BYTE, WORD, DWORD, CHAR, BOOL, LPBYTE

import time
import sys
import threading
import logging

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from python_dll_loader import *
import custom_der_decoders

bcm_logger = logging.getLogger(__name__)
SERIAL_MODE = True

def bcm_error_handler(bcm_error):
    if bcm_error != BCM_ERR_Enum.BCM_NoError:
        bcm_logger.error(f"Beacon Manager Error {bcm_error}: {BCMError.get_error_description(bcm_error)}")
        # Handle error case if needed
        raise Exception(f"Beacon Manager Error {bcm_error}: {BCMError.get_error_description(bcm_error)}")
def cb_error_handler(callback_code, error_code):
    if callback_code == BCM_CALLBACK_Enum.BCM_CB_ERR:
        # No Exception/Error is raised on callbacks.
        # We only log them
        bcm_logger.error(f"Callback Error ({callback_code}) occurred, with error code {error_code}")
        raise Exception(f"Callback Error ({callback_code}) occurred! Error code: {error_code}")

# Defining the BeaconManager class
class BeaconManager:
    def __init__(self, external_callback:callable = None, external_alarm:callable = None):
        self.beacon_state_ok_trigger = threading.Event()
        self.callback_received_notifier = threading.Condition()

        self.external_callback = external_callback
        self.external_alarm = external_alarm

        # This is the BCM structure pointer. It is managed by the DLL
        self.reg_ptr = ST_BCM_REG_PTR()
        # Last received VST
        self.last_vst = []
        
        # PDU cannot be 0 or 1
        pdu = 0x2
        # PDU is at most 4 bits
        pdu &= 0xF
        # The fragmentation header is 0b1xxxx001, where xxxx is the PDU
        self.frag_header = 0x81 | (pdu << 3)
        
        self.c_callback = BCM_CB_HANDLER(self.bcm_callback)
        self.c_alarm = BCM_ALARM_HANDLER(self.bcm_alarm)
        
        bcm_logger.debug("Initializing GEA BCM...")
        
        beacon_state_polling_ms = 100
        send_event_polling_OK = True
        # The user registration number is not used internally by the BCM DLL
        # It is thus free for use in our application
        user_registration = 7
        user_params = None
        if SERIAL_MODE:
            serial_port = 1
            serial_port_speed = BaudRate_Enum.BCM_CFG_115200
            result = bcm_init_manager_fnc(
                ctypes.byref(self.reg_ptr),
                user_registration,
                user_params,
                serial_port,
                serial_port_speed,
                BCM_STATION_Enum.BCM_Secondary,
                beacon_state_polling_ms,
                send_event_polling_OK,
                self.c_callback,
                self.c_alarm
            )
        else:
            beacon_ip_address = '133.38.40.152'.encode('utf-8')
            beacon_tcp_port = 10001

            result = bcm_init_manager_fnc_ip(
                ctypes.byref(self.reg_ptr),
                user_registration,
                user_params,
                beacon_ip_address,
                beacon_tcp_port,
                BCM_STATION_Enum.BCM_Secondary,
                beacon_state_polling_ms,
                send_event_polling_OK,
                self.c_callback,
                self.c_alarm
            )

        bcm_error_handler(result)
        self.handle_init_errors()

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
            bcm_logger.debug(f"CB: Error, with code {error_code}")
            bcm_logger.error(error_code)
            return
    def bcm_alarm(self, reg_ptr, alarm_type, alarm_state):
        bcm_logger.debug("AL: Alarm notification received!")
        if callable(self.external_alarm):
            bcm_logger.debug("AL: External alarm function present! (from the frontend, for exemple)")
            bcm_logger.debug("AL: We now call/notify it!")
            self.external_alarm(alarm_type, alarm_state)

        if alarm_type == BCM_ALARMS_Enum.BCM_AlarmPeriph or alarm_type == BCM_ALARMS_Enum.BCM_AlarmBeacon:
            bcm_logger.error(f"Alarm error! ({alarm_type})!")
            bcm_logger.debug(f"Alarm description: {BCM_Alarm.get_description(alarm_type)}")
            return
        bcm_logger.debug(f"Alarm received ({alarm_type})!")
        bcm_logger.debug(f"Alarm description: {BCM_Alarm.get_description(alarm_type)}")
        if alarm_type == BCM_ALARMS_Enum.BCM_EventPollingOK:
            self.beacon_state_ok_trigger.set()
        return
    def handle_init_errors(self):
        """This function handles initialization issues, like:
            Unclosed transactions
            Beacon not in stopped mode
            etc."""

        bcm_logger.debug("Getting beacon state...")
        result = self.check_state()
        bcm_logger.debug(self.bcm_state)

        if result == BCM_ERR_Enum.BCM_NoError:
            pass
        elif result == BCM_ERR_Enum.BCM_SocketNotConnected:
            bcm_logger.error("Wait for socket to connect before sending commands!")
            self.wait_until_ok()
        else:
            bcm_logger.error("We could not handle the error, so it will be raised")
            bcm_error_handler(result)

        # If a previous transaction was not closed, we forcefully reset the beacon
        if self.bcm_state.trxInProgress:
            bcm_logger.error("Previously unclosed transaction in progress!")
            bcm_logger.info("We will forcefully reset the beacon...")
            self.reset_manager()
            
            self.wait_until_ok()

        if self.bcm_state.mode != 0:
            self.change_mode(BCM_MODE_Enum.BCM_MOD_Stopped)
            bcm_logger.debug("Changed mode to stopped!")
            #self.close()

    def wait_until_ok(self):
        bcm_logger.debug("Polling the beacon state until it is in an OK state...")
        self.beacon_state_ok_trigger.wait()
        bcm_logger.debug("Beacon is OK!!!")

    def display_cb_event_trigger(self):
        bcm_logger.debug("\tWaiting for CB notification...")
        with self.callback_received_notifier:
            self.callback_received_notifier.wait()
        bcm_logger.debug("\tCB notification received!!! You can receive a VST now.")
        
    def check_state(self):
        self.bcm_state = ST_BCM_STATE()
        
        result = bcm_check_state(self.reg_ptr, ctypes.byref(self.bcm_state))
        
        return result
    
    def get_config(self):
        bcm_config = ST_BCM_CONFIG()
        
        result = bcm_get_config(self.reg_ptr, ctypes.byref(bcm_config))
        bcm_error_handler(result)

        return bcm_config
    
    def change_mode(self, mode_code):
        result = bcm_change_mode(self.reg_ptr, mode_code)
        bcm_error_handler(result)
    def close(self):
        result = bcm_close_manager(ctypes.byref(self.reg_ptr))
        bcm_error_handler(result)
        
    def reset_manager(self):
        result = bcm_reset(self.reg_ptr)
        bcm_error_handler(result)
    
    # Start sending a BST
    def start_bst(self, manufacturer_id=0x31, individual_id=0x111, mandapplications=[1, 20, 29], profile=0x00, profile_list=[0x00], non_mand_applications = [], bst_type:int = BCM_BST_TYPE_Enum.BCM_BST_ChangeBID):
        bst_datagram = custom_der_decoders.encode_bst_datagram(self.frag_header, manufacturer_id, individual_id, mandapplications, profile, profile_list, non_mand_applications)
        if len(bst_datagram) > BCM_SIZEMAX_Enum.BCM_SIZEMAX_BST:
            bcm_logger.error(f"Datagram is too big! Will probably cause a BST error")
        self.start_bst_wrapper(bytes(bst_datagram), bst_type)
        
    def start_bst_wrapper(self, bst_datagram:bytes, bst_type:int):
        bst_datagram_buffer = ctypes.create_string_buffer(bst_datagram, size=len(bst_datagram))
        # Pointer to the buffered BST datagram
        lp_bst_datagram = ctypes.cast(bst_datagram_buffer, POINTER(BYTE))
        byte_bst_type = BYTE(bst_type)

        result = bcm_start_bst(self.reg_ptr,
                               lp_bst_datagram,
                               DWORD(len(bst_datagram)),
                               byte_bst_type)

        bcm_logger.debug("ST_BCM_REG (dereferenced value):")
        bcm_logger.debug(ctypes.cast(self.reg_ptr, ctypes.c_void_p).value)
        bcm_logger.debug(self.reg_ptr.contents)
        
        bcm_error_handler(result)
    
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

        # Converting VST to bytes structure
        self.last_vst = bytes(received_vst_list)

        # Log the VST
        bcm_logger.debug("VST response buffer pointer contents in hex format:")
        bcm_logger.debug(self.last_vst.hex().upper())
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
        return response_as_list
    
    def send_get_request(self, eid, access_credentials=None, attribute_ids=None, close = False):
        datagram = custom_der_decoders.encode_get_request_datagram(self.frag_header, eid, access_credentials, attribute_ids, close)
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

        self.rnd_rse = custom_der_decoders.encode_date_and_time()
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
        decoded_response = custom_der_decoders.decode_response(self.last_cmd_response)
        if decoded_response is None:
            return
        try:
            return_status = decoded_response["ReturnStatus"]
            raise(return_status)
        except custom_der_decoders.ReturnStatus:
            bcm_logger.error(return_status.message)
        decoded_response
        



    def close_transaction(self, close_transaction = False):
        self.set_mmi(True)