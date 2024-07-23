import os
try:
    os.environ['MK_PATH']
except:
    os.environ['MK_PATH'] = r"C:\Users\wesley.rodrigues\AXXES\OBU Proxy - Documents\16 - Automatisation des Tests\master_keys_test.json"

import threading
import logging
import custom_der_decoders
import key_derivation

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from python_dll_loader import *
from BeaconManager import BeaconManager

root_logger = logging.getLogger()

console_handler = logging.StreamHandler()
file_handler = logging.FileHandler('gea_bcm_dll_python_loader.log')

class ColoredFormatterWrapper(logging.Formatter):
    GRAY = "\033[38m"
    YELLOW = "\033[33m"
    RED = "\033[31;20m"
    BOLD_RED = "\033[31m"
    BLUE = "\33[34m"
    RESET_COLOR = "\033[0m"
    default_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)")
    formatter = None

    LEVEL_COLORS = {
        logging.DEBUG: GRAY,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def __init__(self, formatter=default_formatter):
        self.formatter = formatter

    def format(self, record):
        color = ColoredFormatterWrapper.LEVEL_COLORS.get(record.levelno)
        colored_formatting = color + self.formatter.format(record) + ColoredFormatterWrapper.RESET_COLOR
        return colored_formatting
        
console_formatter = ColoredFormatterWrapper(logging.Formatter("%(levelname)-8s - %(threadName)s - %(message)s"))
console_handler.setFormatter(console_formatter)

file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)

root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)
root_logger.setLevel(logging.DEBUG)

def main():
    root_logger.debug("Instantiating BeaconManager class...")
    beacon_manager = BeaconManager()
    root_logger.debug("Initialized BCM!!")

    root_logger.debug("Getting beacon configuration...")
    root_logger.debug("Displaying config data...:\n" + repr(beacon_manager.get_config()))
    
    beacon_manager.change_mode(BCM_MODE_Enum.BCM_MOD_Transparent)
    root_logger.debug("Changed mode to transparent!")
    root_logger.debug("Getting beacon state...")
    bcm_state = beacon_manager.check_state()
    root_logger.debug(bcm_state)

    root_logger.debug("Starting BST...")
    manufacturer_id = 0x00D0
    individual_id = 0xBA00
    #requested_aids = [1, 20, 29]
    #beacon_manager.start_bst(manufacturer_id, individual_id, requested_aids)
    beacon_manager.start_bst()
    
    root_logger.debug("No errors occurred: BST started!")
    root_logger.debug("We now create a task that logs some text to the console upon receiving a callback...")
    event_thread = threading.Thread(target = beacon_manager.display_cb_event_trigger)
    event_thread.start()
    root_logger.debug("Number of threads: " + str(threading.active_count()))

    root_logger.info("We now wait on the main thread until we receive a VST...")
    beacon_manager.wait_and_get_vst()

    root_logger.debug("Last VST details in raw bytes format:")
    root_logger.debug(beacon_manager.last_vst)
    root_logger.debug("We now decode the VST")
    vst_data = custom_der_decoders.decode_vst(beacon_manager.last_vst)
    root_logger.debug(vst_data)

    eid = 4
    root_logger.debug(f"Getting the attribute 32=0x20, PaymentMeans, for the instance with EID {eid}...")
    response = beacon_manager.send_get_request(eid, attribute_ids=[0x20])
    root_logger.debug(f"BCM last command response in hex format: {beacon_manager.last_cmd_response.hex().upper()}")

    eid = 7
    vst_application_index = -1
    for index, application in enumerate(vst_data['applications']):
        if application["EID"] == eid:
            vst_application_index = index
    
    if vst_application_index == -1:
        root_logger.info(f"EID 7 is not present!")

    # EID 7 is present! The beacon operator can do a transaction
    elif vst_application_index > 0:
        root_logger.debug(f"Operator application index: {vst_application_index}")
        operator_application = vst_data['applications'][vst_application_index]

        efc_cm = operator_application['EFC-CM']
        root_logger.debug(f"EFC-CM decoding: {custom_der_decoders.DSRC_Data_Container(bytes.fromhex("20" + efc_cm)).__repr__()}")

        root_logger.debug(f"AC_CR-KeyRef in hex: {operator_application["AC_CR-KeyRef"]:04X}")
        ac_cr_key_ref = operator_application["AC_CR-KeyRef"]

        rnd_obe = operator_application["RndOBE"]
        contract_provider = efc_cm[0:6]
        access_credentials = key_derivation.compute_access_credentials(contract_provider, rnd_obe, ac_cr_key_ref)
        root_logger.debug(f"Generated Access Credentials in hex format: {access_credentials:08X}")

        # Operator auth key is optional, it is set to 111 by default
        #response = beacon_manager.presentation_request(eid, access_credentials, 111, [0])
        
        attribute_list_start_index = 10
        #attribute_list = custom_der_decoders.decode_attributes_list(response, attribute_list_start_index)
        #root_logger.debug(f"AttributeList in hex: {attribute_list}")


        root_logger.debug(f"Sending a GET request on EID {eid} for attribute 16, the LPN")
        response = beacon_manager.send_get_request(eid, access_credentials, [16])
        root_logger.info(f"GET.response decoded: {custom_der_decoders.decode_response(response)}")
        #root_logger.debug(f"Latest sent command decoded AttributesList: {beacon_manager.decode_last_get_response()}")

        root_logger.debug(f"LPN decoding: {custom_der_decoders.DSRC_Data_Container(bytes.fromhex("20" + efc_cm)).__repr__()}")
        root_logger.debug(f"Sending a GET request on EID {eid} for multiple attributes at once")
        
        response = beacon_manager.send_get_request(eid, access_credentials, [0, 16, 17, 20, 26, 33, 34])
        root_logger.info(f"GET.response decoded: {custom_der_decoders.decode_response(response)}")
        
        root_logger.debug(f"Sending a GET_STAMPED request on EID {eid} for attribute 32, the PaymenMeans")
        response = beacon_manager.presentation_request(eid, access_credentials, [32])
        decoded_get_stamped_response = custom_der_decoders.decode_response(response)
        root_logger.info(f"GET_STAMPED.response decoded: {decoded_get_stamped_response}")

        size = decoded_get_stamped_response['ResponseParameter']['AttributeList_size']
        provided_authenticator = decoded_get_stamped_response['ResponseParameter']['Authenticator']
        attribute_list_bytes = bytes(response[4 : 4 + size])
        root_logger.debug(f"AttibuteList in hex: {attribute_list_bytes.hex().upper()}")
        rnd_rse = beacon_manager.rnd_rse
        root_logger.debug(f"RndRSE value: {rnd_rse:04X}")

        pan_id = decoded_get_stamped_response['ResponseParameter']['AttributeList'][0]['representation']['PAN']
        print("PAN ID:", pan_id)

        authenticator = key_derivation.compute_authenticator_with_auk_ref(pan_id, contract_provider, attribute_list_bytes, rnd_rse, 115)
        root_logger.debug(f"Authenticator provided by OBE: {provided_authenticator:08X}")
        root_logger.debug(f"Authenticator computed by RSE: {authenticator:08X}")

        if provided_authenticator != authenticator:
            root_logger.error(f"The OBE is fraudulent!!")
        else:
            root_logger.info(f"OBE is authentic!!!")


    root_logger.debug("We should send a SetMMI command on the main Thread to close the transaction")
    root_logger.debug("Otherwise, the transaction will remain unclosed and cause an error on the next execution")
    beacon_manager.set_mmi(True)


# Main execution
if __name__ == "__main__":
    main_thread = threading.Thread(target=main)
    main_thread.start()
