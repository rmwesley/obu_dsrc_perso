import os
import json

try:
    os.environ['MK_PATH']
except:
    os.environ['MK_PATH'] = r"..\master_keys.json"

import threading
import logging
import custom_der_decoders
import dsrc_security

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from gea_bcm_dll_loader import *
from beacon_manager import BeaconManager

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# SETTING UP COLORED CONSOLE LOGGING
console_handler = logging.StreamHandler()
class ColoredFormatterWrapper(logging.Formatter):
    GRAY = "\033[38m"
    YELLOW = "\033[33m"
    RED = "\033[31;20m"
    BOLD_RED = "\033[31m"
    BLUE = "\33[34m"
    RESET_COLOR = "\033[0m"
    default_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)")
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
console_formatter = ColoredFormatterWrapper(logging.Formatter(f"%(levelname)-8s %(filename)22s:%(lineno)-4s - %(threadName)s: %(message)s"))
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)

# SETTING UP LOGGER FILE HANDLER
file_handler = logging.FileHandler('gea_bcm_dll_python_loader.log')
file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)
root_logger.addHandler(file_handler)

def callback_logger(cb_code, error_code):
    if cb_code == BCM_CALLBACK_Enum.BCM_CB_ERR:
        root_logger.error(f"Callback Error ({cb_code}) occurred, with error code {error_code}")
        return
    root_logger.debug(f"Callback IN ({cb_code})")
    root_logger.debug(BCM_Callback.get_description(cb_code))

def main():
    root_logger.debug("Instantiating BeaconManager class...")
    beacon_manager = BeaconManager()
    root_logger.debug("Initialized BCM!!")

    root_logger.debug("Getting beacon configuration...")
    bcm_config = beacon_manager.get_config()
    root_logger.debug(f"Displaying config data...: {bcm_config}")
    
    beacon_manager.change_mode(BCM_MODE_Enum.BCM_MOD_Transparent)
    root_logger.debug("Changed mode to transparent!")
    
    root_logger.debug("Getting beacon state...")
    result = beacon_manager.update_state()
    root_logger.debug(beacon_manager.beacon_state)

    root_logger.debug("We now update/get the BeaconID according to the beacon before sending the BST")
    result = beacon_manager.update_beacon_id()
    root_logger.debug(f"BeaconID according to beacon: {beacon_manager.last_beacon_id.hex().upper()}")

    root_logger.debug("Initialization: Starting BST and getting VST...")
    # vst_obj = beacon_manager.initialization(0x221, 0x277, mandapplications= [20], bst_type=BCM_BST_TYPE_Enum.BCM_BST_ChangeBID)
    vst_obj = beacon_manager.initialization(0x221, 0x277, mandapplications= [1, 20], bst_type=BCM_BST_TYPE_Enum.BCM_BST_ChangeBID)

    # Requesting EFC, CCC and UNI
    required_applications = [1, 20, 29]
    #Requesting only CCC
    #required_applications = [20]
    root_logger.info(f"Preparing a BST requesting AIDs {required_applications}")

    READ_TIS = True
    if READ_TIS:
        eid = 4
        root_logger.debug(f"Getting the attribute 32=0x20, PaymentMeans, for the instance with EID {eid}...")
        response = beacon_manager.send_get_request(eid, attribute_ids=[0x20])
        decoded_get_response = custom_der_decoders.decode_response(response)
        root_logger.info(f"GET.response decoded: {json.dumps(decoded_get_response, indent=2)}")

    eid = 2
    vst_application_index = vst_obj.get_eid_info(eid)

    # The EID is present in the VST! The beacon operator can do a transaction
    if vst_application_index >= 0:
        root_logger.debug(f"Operator application index: {vst_application_index}")
        operator_application = vst_obj['Applications'][vst_application_index]

        efc_cm = operator_application['EFC-CM']
        root_logger.debug(f"EFC-CM decoding: {custom_der_decoders.DSRC_Data_Container(bytes.fromhex("20" + efc_cm)).__repr__()}")

        root_logger.debug(f"AC_CR-KeyRef in hex: {operator_application["AC_CR-KeyRef"]:04X}")
        ac_cr_key_ref = operator_application["AC_CR-KeyRef"]

        rnd_obe = operator_application["RndOBE"]
        access_credentials = dsrc_security.compute_access_credentials(efc_cm, rnd_obe, ac_cr_key_ref)
        root_logger.debug(f"Generated Access Credentials in hex format: {access_credentials:08X}")

        # Operator auth key is optional, it is set to 111 by default
        #response = beacon_manager.presentation_request(eid, access_credentials, 111, [0])
        
        attribute_list_start_index = 10
        #attribute_list = custom_der_decoders.decode_attributes_list(response, attribute_list_start_index)
        #root_logger.debug(f"AttributeList in hex: {attribute_list}")


        root_logger.info(f"Sending a GET request on EID {eid} for attribute 16, the LPN")
        response = beacon_manager.send_get_request(eid, access_credentials, [16])
        decoded_get_response = custom_der_decoders.decode_response(response)
        root_logger.info(f"GET.response decoded: {json.dumps(decoded_get_response, indent=2)}")
        #root_logger.debug(f"Latest sent command decoded AttributesList: {beacon_manager.decode_last_get_response()}")

        decoded_lpn = custom_der_decoders.DSRC_Data_Container(bytes.fromhex("20" + efc_cm)).__repr__()
        root_logger.debug(f"LPN decoding: {json.dumps(decoded_lpn, indent=2)}")
        
        # CARDME transaction required attributes
        #root_logger.debug(f"Sending a GET request on EID {eid} for multiple attributes at once")
        cardme_attribute_list = [0, 16, 17, 20, 26, 33, 34]
        belgium_attribute_list = [0, 16, 17, 20]
        attribute_list = belgium_attribute_list
        root_logger.info(f"Sending a GET request on EID {eid} for attributes {attribute_list}")
        response = beacon_manager.send_get_request(eid, access_credentials, attribute_list)
        decoded_get_response = custom_der_decoders.decode_response(response)
        root_logger.info(f"GET.response decoded: {json.dumps(decoded_get_response, indent=2)}")
        
        root_logger.debug(f"Sending a GET_STAMPED request on EID {eid} for attribute 32, the PaymenMeans")
        response = beacon_manager.presentation_request(eid, access_credentials, [32])
        decoded_get_stamped_response = custom_der_decoders.decode_response(response)
        root_logger.info(f"GET_STAMPED.response decoded: {json.dumps(decoded_get_stamped_response, indent=2)}")

        if decoded_get_stamped_response is not None:
            size = decoded_get_stamped_response['ResponseParameter']['AttributeList_size']
            provided_authenticator = decoded_get_stamped_response['ResponseParameter']['Authenticator']
            attribute_list_bytes = bytes(response[4 : 4 + size])
            root_logger.debug(f"AttibuteList in hex: {attribute_list_bytes.hex().upper()}")
            rnd_rse = beacon_manager.rnd_rse
            root_logger.debug(f"RndRSE value: {rnd_rse:04X}")

            pan_id = decoded_get_stamped_response['ResponseParameter']['AttributeList'][0]['representation']['PAN']
            print("PAN ID:", pan_id)

            authenticator = dsrc_security.compute_authenticator_with_auk_ref(pan_id, efc_cm, attribute_list_bytes, rnd_rse, 115)
            root_logger.debug(f"Authenticator provided by OBE: {provided_authenticator:08X}")
            root_logger.debug(f"Authenticator computed by RSE: {authenticator:08X}")

            if provided_authenticator != authenticator:
                root_logger.error(f"The OBE is fraudulent!!")
            else:
                root_logger.info(f"OBE is authentic!!!")


    root_logger.debug("We should send a SetMMI command on the main Thread to close the transaction")
    root_logger.debug("Otherwise, the transaction will remain unclosed and cause an error on the next execution")
    beacon_manager.set_mmi(True)
    root_logger.info(f"VST: {json.dumps(vst_obj, indent=2)}")

# Main execution
if __name__ == "__main__":
    main_thread = threading.Thread(target=main)
    main_thread.start()