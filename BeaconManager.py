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

def bcm_error_logger(bcm_error):
    bcm_logger.error(f"Beacon Manager Error {bcm_error}: {BCMError.get_error_description(bcm_error)}")

def bcm_error_handler(bcm_error):
    if bcm_error != BCM_ERR_Enum.BCM_NoError:
        bcm_error_logger(bcm_error)
        # Handle error case if needed
        raise Exception(f"Beacon Manager Error {bcm_error}: {BCMError.get_error_description(bcm_error)}")

def cb_error_logger(cb_error):
    bcm_logger.error(f"Callback Error ({cb_error}) occurred")

def cb_error_handler(cb_error):
    if cb_error == BCM_CALLBACK_Enum.BCM_CB_ERR:
        # No Exception/Error is raised on callbacks.
        # We only log them
        raise Exception(f"Callback Error ({cb_error}) occurred")
    
callback_received_evt = threading.Event()
# As those callback functions are directly called by the internal thread which is
# managing the communication with the beacon, they should return as
# quickly as possible
def callback(reg_ptr, callback_type, error_code):
    bcm_logger.debug("CB: Callback notification received!")
    try:
        cb_error_handler(callback_type)
        bcm_error_handler(error_code)
        bcm_logger.debug("CB: OK! No error occurred in callback: This means a VST was received!")
        bcm_logger.debug("CB: We thus set the callback_received_evt event")
        callback_received_evt.set()
    except:
        bcm_logger.debug("CB: An error occurred during the callback...")
        return
def alarm(reg_ptr, alarm_type, state):
    bcm_logger.debug("AL: Alarm")

# Defining the BeaconManager class
class BeaconManager:
    
    def handle_init_errors(self):
        """This function handles initialization issues, like:
            Unclosed transactions
            Beacon not in stopped mode
            etc."""

        bcm_logger.debug("Getting beacon state...")
        bcm_state = self.check_state()
        bcm_logger.debug(bcm_state)

        # If a previous transaction was not closed, we forcefully reset the beacon
        if bcm_state.trxInProgress:
            bcm_logger.debug("Previously unclosed transaction in progress!")
            bcm_logger.debug("We will forcefully reset the beacon...")
            self.reset_manager()
            bcm_logger.debug("Try executing the program again soon.")
            sys.exit(1)
        if bcm_state.mode != 0:
            self.change_mode(BCM_MODE_Enum.BCM_MOD_Stopped)
            bcm_logger.debug("Changed mode to stopped!")
            #self.close()

    def __init__(self):
        self.reg_ptr = ST_BCM_REG_PTR()
        self.last_vst = []
        
        # PDU cannot be 0 or 1
        pdu = 0x2
        # PDU is at most 4 bits
        pdu &= 0xF
        # The fragmentation header is 0b1xxxx001, where xxxx is the PDU
        self.frag_header = 0x81 | (pdu << 3)
        
        self.c_callback = BCM_CB_HANDLER(callback)
        self.c_alarm = BCM_ALARM_HANDLER(alarm)
        
        bcm_logger.debug("Initializing GEA BCM...")
        
        result = bcm_init_manager_fnc(
            ctypes.byref(self.reg_ptr), 1, None, 1,
            BaudRate_Enum.BCM_CFG_115200, BCM_STATION_Enum.BCM_Secondary, 3000, False,
            self.c_callback, self.c_alarm
            )

        bcm_error_handler(result)
        self.handle_init_errors()

    
    def display_cb_event_trigger(self):
        bcm_logger.debug("\tWaiting for CB event...")
        callback_received_evt.wait()
        bcm_logger.debug("\tCB event triggered!!! You can receive a VST now.")
        
    def check_state(self):
        bcm_state = ST_BCM_STATE()
        
        result = bcm_check_state(self.reg_ptr, ctypes.byref(bcm_state))
        bcm_error_handler(result)
        
        return bcm_state
    
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
    def wait_for_notification(self):
        callback_received_evt.wait()

    # Wait for a notification then get the VST
    def wait_for_vst(self):
        self.wait_for_notification()
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