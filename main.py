import ctypes
from ctypes import POINTER, wintypes, c_void_p, c_char_p, c_uint, c_int, c_byte, c_bool, c_ulong, c_ushort
from ctypes.wintypes import HWND, LPCWSTR, UINT, BYTE, WORD, DWORD, CHAR, BOOL, LPBYTE

import time

# Importing the definitions of the Python DLL wrapper, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from python_dll_wrapper import *


def callback(reg_ptr, callback_type, error_code):
    print("VST received")
def alarm(reg_ptr, alarm_type, state):
    print("Alarm")

# Define your BeaconManager class and instantiate it
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

        error_code = bcm_init_manager_fnc(ctypes.byref(self.reg_ptr), 1, None, 1, BaudRate_Enum.BCM_CFG_115200, BCM_STATION_Enum.BCM_Secondary, 3000, False, self.c_callback, self.c_alarm)
        print(f"[Error {error_code}]: {BCMError.get_error_description(error_code)}")

    def start_bst(self, manufacturer_id, individual_id, mandapplications, profile=0x00, profile_list=[0x00], non_mand_applications = []):
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
        
        print(hex(beacon_id_int))
        beacon_id = list(beacon_id_int.to_bytes(6))
        
        utc_timestamp = list(int(time.time()).to_bytes(4))
        if non_mand_applications_present :
            bst_datagram = [self.frag_header] + beacon_id + utc_timestamp + [profile] + [len(mandapplications)] + mandapplications + [len(non_mand_applications)] + non_mand_applications + profile_list
        else:
            bst_datagram = [self.frag_header] + beacon_id + utc_timestamp + [profile] + [len(mandapplications)] + mandapplications + profile_list
        
        # Pointer to the BST datagram
        #byte_array_bst_datagram = (BYTE * len(bst_datagram))(*bst_datagram)
        #lp_bst_datagram = ctypes.cast(byte_array_bst_datagram, POINTER(BYTE))
        lp_bst_datagram = ctypes.cast(bytes(bst_datagram), POINTER(BYTE))

        # Print the datagram elements in hex:
        #print('BST datagram list in hex:', '[{}]'.format(', '.join(hex(x) for x in bst_datagram)))
        # print(type(bst_datagram))
        # print('BST datagram array in hex:', '[{}]'.format(', '.join(hex(x) for x in byte_array_bst_datagram)))
        # print(type(byte_array_bst_datagram))
        # print('BST datagram pointer array in hex:', '[{}]'.format(', '.join(hex(lp_bst_datagram[i]) for i in range(0, len(bst_datagram)))))
        # print(lp_bst_datagram)
        print(bytes(bst_datagram).hex())
        
        #lp_bst_datagram = ctypes.create_string_buffer(bytes(bst_datagram), len(bst_datagram))
        #new_lp_bst_datagram = lp_bst_datagram
        #new_lp_bst_datagram = ctypes.cast(lp_bst_datagram, LPBYTE)

        
        #ctypes.windll.msvcrt.printf("%s", lp_bst_datagram)
        #ctypes.windll.msvcrt.printf("1000000")
        #print(type(lp_bst_datagram))
        #print(self.reg_ptr, lp_bst_datagram, len(bst_datagram), BCM_BST_TYPE_Enum.BCM_BST_Normal)
        result = bcm_start_bst(self.reg_ptr, lp_bst_datagram, DWORD(len(bst_datagram)), BCM_BST_TYPE_Enum.BCM_BST_Normal);
        return result

# Example callback function to handle DSRC operations
# def dsrc_callback(data_ptr, data_size):
    # # Implement your DSRC handling logic here
    # print(f"Received DSRC data of size {data_size} bytes")
    # data_buffer = ctypes.cast(data_ptr, ctypes.POINTER(ctypes.c_byte * data_size)).contents
    # print(f"Data received: {data_buffer}")
    # # Process the received DSRC data according to ISO 14906 and CEN 15509

# Main execution
if __name__ == "__main__":
    beacon_manager = BeaconManager()
    result = beacon_manager.start_bst(0xD00D, 0xBAAD, [0x10])
    
    if result != BCM_ERR_Enum.BCM_NoError:
        print(f"Error initializing BST: {result}: {BCMError.get_error_description(result)}")
        # Handle error case if needed
    else:
        print("Manager initialized successfully")
        # Perform DSRC operations
        # For simplicity, let's assume initiating a DSRC GET request
        # Example: Send a DSRC GET request
        # Your logic here to trigger a DSRC GET request using the initialized BeaconManager and callback function
        # For demonstration, we'll pretend to receive some DSRC data
        #dsrc_data = [0x01, 0x02, 0x03]  # Example DSRC data received
        #dsrc_callback(ctypes.byref((ctypes.c_byte * len(dsrc_data))(*dsrc_data)), len(dsrc_data))
