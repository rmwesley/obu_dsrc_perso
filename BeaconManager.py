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

bcm_logger = logging.getLogger(__name__)
SERIAL_MODE = True

def bcm_error_logger(bcm_error):
    bcm_logger.error(f"Beacon Manager Error {bcm_error}: {BCMError.get_error_description(bcm_error)}")

def bcm_error_handler(bcm_error):
    if bcm_error != BCM_ERR_Enum.BCM_NoError:
        bcm_error_logger(bcm_error)
        # Handle error case if needed
        raise Exception(f"Beacon Manager Error {bcm_error}: {BCMError.get_error_description(bcm_error)}")

def callback_logger(cb_code, error_code):
    if cb_code == BCM_CALLBACK_Enum.BCM_CB_ERR:
        bcm_logger.error(f"Callback Error ({cb_code}) occurred, with error code {error_code}")
        bcm_error_logger(error_code)
        return
    bcm_logger.debug(f"Callback IN ({cb_code})")
    bcm_logger.debug(BCM_Callback.get_description(cb_code))

def cb_error_handler(callback_code, error_code):
    if callback_code == BCM_CALLBACK_Enum.BCM_CB_ERR:
        # No Exception/Error is raised on callbacks.
        # We only log them
        raise Exception(f"Callback Error ({callback_code}) occurred! Error code: {error_code}")

def alarm_logger(alarm_code):
    if alarm_code == BCM_ALARMS_Enum.BCM_AlarmPeriph or alarm_code == BCM_ALARMS_Enum.BCM_AlarmBeacon:
        bcm_logger.error(f"Alarm error! ({alarm_code})!")
        bcm_logger.debug(f"Alarm description: {BCM_Alarm.get_description(alarm_code)}")
        return
    bcm_logger.debug(f"Alarm received ({alarm_code})!")
    bcm_logger.debug(f"Alarm description: {BCM_Alarm.get_description(alarm_code)}")

# Defining the BeaconManager class
class BeaconManager:
    # Defining the Callback and Alarm (they are both callback functions)
    # But alarm has a state
    # As those callback functions are directly called by the internal thread which is
    # managing the communication with the beacon they should return as
    # quickly as possible
    def bcm_callback(self):
        def callback(reg_ptr, callback_type, error_code):
            bcm_logger.debug("CB: Callback notification received!")
            try:
                cb_error_handler(callback_type, error_code)
                bcm_error_handler(error_code)
                bcm_logger.debug("CB: OK! No error occurred in callback: This means a VST was received!")
                bcm_logger.debug("CB: We thus notify all threads waiting on the callback_received_notifier condition")
                with self.callback_received_notifier:
                    self.callback_received_notifier.notify_all()
            except:
                bcm_logger.debug(f"CB: Error, with code {error_code}")
                bcm_error_logger(error_code)
                return
        return callback
        
    def bcm_alarm(self):
        def alarm(reg_ptr, alarm_type, alarm_state):
            alarm_logger(alarm_type)

            if alarm_type == BCM_ALARMS_Enum.BCM_EventPollingOK:
                self.beacon_state_ok_trigger.set()

            self.last_alarm = {
                "Alarm": alarm_type,
                "State": alarm_state
                }
        return alarm
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

    def __init__(self):
        self.beacon_state_ok_trigger = threading.Event()
        self.callback_received_notifier = threading.Condition()

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
        
        self.c_callback = BCM_CB_HANDLER(self.bcm_callback())
        self.c_alarm = BCM_ALARM_HANDLER(self.bcm_alarm())
        
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
    def start_bst(self, manufacturer_id, individual_id, mandapplications=[1, 20, 29], profile=0x00, profile_list=[0x00], non_mand_applications = [], bst_type = BCM_BST_TYPE_Enum.BCM_BST_ChangeBID):
        # INITIALIZATION.request is 0b1000, shifted 4 bits
        init_request = 0x80
        
        # 1 bit boolean
        non_mand_applications_present = len(non_mand_applications) != 0
        # Shift it 3 bits to the left to fit the datagram
        non_mand_applications_present = non_mand_applications_present << 3
        
        beacon_id_int = (init_request | non_mand_applications_present) << 40
        
        # manufacturerId has a size of 16 bits
        beacon_id_int |= manufacturer_id << 27
        # individualId has a size of 27 bits
        beacon_id_int |= individual_id
        
        beacon_id = list(beacon_id_int.to_bytes(6))
        
        utc_timestamp = list(int(time.time()).to_bytes(4))
        if non_mand_applications_present :
            bst_datagram = [self.frag_header] + beacon_id + utc_timestamp + [profile] + [len(mandapplications)] + mandapplications + [len(non_mand_applications)] + non_mand_applications + profile_list
        else:
            bst_datagram = [self.frag_header] + beacon_id + utc_timestamp + [profile] + [len(mandapplications)] + mandapplications + profile_list
        
        bst_datagram_buffer = ctypes.create_string_buffer(bytes(bst_datagram), size=len(bst_datagram))
        # Pointer to the buffered BST datagram
        lp_bst_datagram = ctypes.cast(bst_datagram_buffer, POINTER(BYTE))
        
        bcm_logger.debug("BST to be sent in hex:")
        bcm_logger.debug(bytes(bst_datagram).hex())
        
        bst_repr = f'''
        Init request + Non_mand_present_bool + Beacon ID: { hex(beacon_id_int)[2:].upper() }
        Profile: {profile_list}
        Requested AIDs: {mandapplications}
        Requested optional AIDs: {non_mand_applications}
        Profile List: {profile_list}'''

        bcm_logger.debug("Detailed BST string representation:")
        bcm_logger.debug(bst_repr)

        if len(bst_datagram) > BCM_SIZEMAX_Enum.BCM_SIZEMAX_BST:
            bcm_logger.error(f"Datagram is too big! Will probably cause a BST error")

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
        
        vst_max_size = BCM_SIZEMAX_Enum.BCM_SIZEMAX_ANSWER
        dword_max_size = DWORD(vst_max_size)
        vst_answer_buffer_array = ctypes.create_string_buffer(vst_max_size)
        vst_answer_size = DWORD()

        # Pointer where the VST datagram answer will be stored by BCM
        lp_vst_response_datagram = ctypes.cast(vst_answer_buffer_array, POINTER(BYTE))
        
        result = bcm_get_vst(self.reg_ptr,
                             lp_vst_response_datagram,
                             ctypes.byref(vst_answer_size),
                             dword_max_size)
        
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

    def set_mmi(self, close = False):
        # SetMMI ActionType is 0xA, or 10 in decimal
        set_mmi_datagram = [self.frag_header, 0x05, 0x00, 0x0A, 0x00, 0x00]
        set_mmi_datagram_buffer = ctypes.create_string_buffer(bytes(set_mmi_datagram), size=len(set_mmi_datagram))
        lp_cmd_datagram = ctypes.cast(set_mmi_datagram_buffer, POINTER(BYTE))

        cmd_max_size = BCM_SIZEMAX_Enum.BCM_SIZEMAX_CMD
        cmd_buffer_array = ctypes.create_string_buffer(cmd_max_size)
        cmd_buffer_size = DWORD()
        dword_max_size = DWORD(cmd_max_size)
        lp_cmd_response_datagram = ctypes.cast(cmd_buffer_array, POINTER(BYTE))
        
        bcm_send_cmd(self.reg_ptr, lp_cmd_datagram, DWORD(len(set_mmi_datagram)),
		lp_cmd_response_datagram, ctypes.byref(cmd_buffer_size), dword_max_size, close)

    def close_transaction(self, close_transaction = False):
        self.set_mmi(True)