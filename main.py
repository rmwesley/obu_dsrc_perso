import ctypes
from ctypes import POINTER, wintypes, c_void_p, c_char_p, c_uint, c_int, c_byte, c_bool, c_ulong, c_ushort
from ctypes.wintypes import HWND, LPCWSTR, UINT, BYTE, WORD, DWORD, CHAR, BOOL, LPBYTE

import time
import sys
import threading

# Importing the definitions of the Python DLL wrapper, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from python_dll_wrapper import *

def bcm_error_logger(bcm_error):
    print(f"Beacon Manager Error {bcm_error}: {BCMError.get_error_description(bcm_error)}")

def bcm_error_handler(bcm_error):
    if bcm_error != BCM_ERR_Enum.BCM_NoError:
        bcm_error_logger(bcm_error)
        # Handle error case if needed
        raise Exception(f"Beacon Manager Error {bcm_error}: {BCMError.get_error_description(bcm_error)}")

def cb_error_logger(cb_error):
    print(f"Callback Error ({cb_error}) occurred")

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
    print("\tCallback notification received!")
    try:
        cb_error_handler(callback_type)
        bcm_error_handler(error_code)
        print("\tOK! No error occurred in callback: This means a VST was received!")
        print("\tWe thus set the callback_received_evt event")
        callback_received_evt.set()
    except:
        return
def alarm(reg_ptr, alarm_type, state):
    print("\tAlarm")

# Defining the BeaconManager class
class BeaconManager:
    def __init__(self):
        self.reg_ptr = ST_BCM_REG_PTR()
        
        # PDU cannot be 0 or 1
        pdu = 0x2
        # PDU is at most 4 bits
        pdu &= 0xF
        # The fragmentation header is 0b1xxxx001, where xxxx is the PDU
        self.frag_header = 0x81 | (pdu << 3)
        
        self.c_callback = BCM_CB_HANDLER(callback)
        self.c_alarm = BCM_ALARM_HANDLER(alarm)
        print(ctypes.byref(self.reg_ptr))
        
        result = bcm_init_manager_fnc(
            ctypes.byref(self.reg_ptr), 1, None, 1,
            BaudRate_Enum.BCM_CFG_115200, BCM_STATION_Enum.BCM_Secondary, 3000, False,
            self.c_callback, self.c_alarm
            )

        bcm_error_handler(result)

    def display_cb_event_trigger(self):
        print("\tWaiting for CB event...")
        callback_received_evt.wait()
        print("\tCB event triggered!!! You can receive a VST now.")
        
    def check_state(self):
        out_state = ST_BCM_STATE()
        
        result = bcm_check_state(self.reg_ptr, ctypes.byref(out_state))
        
        bcm_error_handler(result)
        return out_state
    def get_config(self):
        config = ST_BCM_CONFIG()
        config_pointer = ctypes.pointer(config)
        
        bcm_get_config(self.reg_ptr, config_pointer)
        str_config = "Config data:\n"
        for field_name, field_type in config_pointer.contents._fields_:
            str_config += f"\t{field_name}: {getattr(config_pointer.contents, field_name)}\n"
        return str_config
    
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
    def start_bst(self, manufacturer_id, individual_id, mandapplications, profile=0x00, profile_list=[0x00], non_mand_applications = [], bst_type = BCM_BST_TYPE_Enum.BCM_BST_ChangeBID):
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
        
        #print(hex(beacon_id_int))
        beacon_id = list(beacon_id_int.to_bytes(6))
        
        utc_timestamp = list(int(time.time()).to_bytes(4))
        if non_mand_applications_present :
            bst_datagram = [self.frag_header] + beacon_id + utc_timestamp + [profile] + [len(mandapplications)] + mandapplications + [len(non_mand_applications)] + non_mand_applications + profile_list
        else:
            bst_datagram = [self.frag_header] + beacon_id + utc_timestamp + [profile] + [len(mandapplications)] + mandapplications + profile_list
        
        bst_datagram_buffer = ctypes.create_string_buffer(bytes(bst_datagram), size=len(bst_datagram))
        # Pointer to the buffered BST datagram
        lp_bst_datagram = ctypes.cast(bst_datagram_buffer, POINTER(BYTE))
        
        print("BST to be sent in hex: ", bytes(bst_datagram).hex())

        if len(bst_datagram) > BCM_SIZEMAX_Enum.BCM_SIZEMAX_BST:
            print(f"Datagram is too big! Will probably cause a BST error")

        byte_bst_type = BYTE(bst_type)
        
        result = bcm_start_bst(self.reg_ptr,
                               lp_bst_datagram,
                               DWORD(len(bst_datagram)),
                               byte_bst_type)
        bcm_error_handler(result)
    
    # Get VST
    # This function should only be called inside the callback declared to the
    # BCM Init Manager
    def get_vst(self):
        print("Getting VST...")
        
        vst_max_size = BCM_SIZEMAX_Enum.BCM_SIZEMAX_ANSWER
        vst_answer_buffer_array = ctypes.create_string_buffer(vst_max_size)
        vst_answer_buffer_size = DWORD()
        dword_max_size = DWORD(vst_max_size)
        # Pointer where the VST datagram anwser will be stored by BCM
        lp_vst_response_datagram = ctypes.cast(vst_answer_buffer_array, POINTER(BYTE))
        
        result = bcm_get_vst(self.reg_ptr,
                             lp_vst_response_datagram,
                             ctypes.byref(vst_answer_buffer_size),
                             dword_max_size)
        print("Handling errors...")
        bcm_error_handler(result)
        print("VST received!")
        # Slicing a ctypes array or pointer will automatically produce a Python list
        received_vst_list = lp_vst_response_datagram[:vst_answer_buffer_size.value]
        # printing the VST in hex format
        print("VST response buffer pointer contents in hex:")
        print(bytes(received_vst_list).hex())
        return vst_answer_buffer_array.value
    def set_mmi(self):
        # SetMMI ActionType is 0xA, or 10 in decimal
        set_mmi_datagram = [self.frag_header, 0x05, 0x00, 0x0A, 0x00, 0x00]
        set_mmi_datagram_buffer = ctypes.create_string_buffer(bytes(set_mmi_datagram), size=len(set_mmi_datagram))
        lp_vst_datagram = ctypes.cast(set_mmi_datagram_buffer, POINTER(BYTE))

        cmd_max_size = BCM_SIZEMAX_Enum.BCM_SIZEMAX_CMD
        cmd_buffer_array = ctypes.create_string_buffer(cmd_max_size)
        cmd_buffer_size = DWORD()
        dword_max_size = DWORD(cmd_max_size)
        lp_cmd_response_datagram = ctypes.cast(cmd_buffer_array, POINTER(BYTE))
        
        bcm_send_cmd(self.reg_ptr, lp_vst_datagram, DWORD(len(set_mmi_datagram)),
		lp_cmd_response_datagram, ctypes.byref(cmd_buffer_size), dword_max_size, True);    


def main():
    print("Initializing Beacon Manager...")
    beacon_manager = BeaconManager()
    print("Initialized BCM!!")

    print("Getting beacon state...")
    bcm_state = beacon_manager.check_state()
    print(bcm_state.state, bcm_state.mode, bcm_state.trxInProgress)

    if bcm_state.trxInProgress:
        print("Previously unclosed transaction in progress!")
        print("We will forcefully reset the beacon...")
        beacon_manager.reset_manager()
        print("Try executing the program again soon.")
        sys.exit(1)
    if bcm_state.mode != 0:
        beacon_manager.change_mode(BCM_MODE_Enum.BCM_MOD_Stopped)
        print("Changed mode to stopped!")
        #beacon_manager.close()
    
    print("Getting beacon configuration...")
    print(beacon_manager.get_config())
    
    beacon_manager.change_mode(BCM_MODE_Enum.BCM_MOD_Transparent)
    print("Changed mode to transparent!")
    print("Getting beacon state...")
    bcm_state = beacon_manager.check_state()
    print(bcm_state.state, bcm_state.mode, bcm_state.trxInProgress)

    print("Starting BST...")
    beacon_manager.start_bst(0x00D0, 0xBA00, [0x01])
    
    print("No errors occurred: BST started!")
    print("We now create a task that logs some text to the console upon receiving a callback...")
    event_thread = threading.Thread(target = beacon_manager.display_cb_event_trigger)
    event_thread.start()
    print("Number of threads:", threading.active_count())
    
    print("We now get the VST on the main Thread")
    beacon_manager.get_vst()
    print("We now send a SetMMI command on the main Thread")
    beacon_manager.set_mmi()

# Main execution
if __name__ == "__main__":
    main_thread = threading.Thread(target=main)
    main_thread.start()
