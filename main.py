import os
import json

try:
    os.environ['MK_PATH']
except:
    os.environ['MK_PATH'] = r"..\master_keys.json"

import threading
import logging
import dsrc_security

from ASN.compiled_DSRC_instances import CCCv4_1 as CCC2019
from ASN.compiled_DSRC_instances import EFCv10_1 as EFC
from ASN.compiled_DSRC_instances import LACv2_1

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from gea_bcm_dll_wrapper import *
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
file_handler = logging.FileHandler('gea_bcm_dll_python_wrapper.log')
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
    bcm_config = beacon_manager.beacon_l7_wrapper.get_config()
    root_logger.debug(f"Displaying config data...: {bcm_config}")
    
    beacon_manager.beacon_l7_wrapper.change_mode(BCM_MODE_Enum.BCM_MOD_Transparent)
    root_logger.debug("Changed mode to transparent!")
    
    root_logger.debug("Getting beacon state...")
    result = beacon_manager.beacon_l7_wrapper.update_state()

    root_logger.debug("We now update/get the BeaconID according to the beacon before sending the BST")
    result = beacon_manager.beacon_l7_wrapper.update_beacon_id()
    EFC.EfcDsrcGeneric.BeaconID.from_uper(beacon_manager.beacon_l7_wrapper.last_beacon_id)
    root_logger.debug(f"Beacon (according to GEA Beacon) encoded in JER: {EFC.EfcDsrcGeneric.BeaconID.to_jer()}")

    root_logger.debug("Initialization: Starting BST and getting VST...")

    # Requesting EFC, CCC and UNI
    required_applications = [1, 20, 29]
    #Requesting only CCC
    #required_applications = [20]
    root_logger.info(f"Preparing a BST requesting AIDs {required_applications}")

    t_apdu_with_vst = beacon_manager.initialize_transaction(mandapplications = required_applications)
    
    READ_TIS = True
    if READ_TIS:
        eid = 4
        root_logger.debug(f"Getting the attribute 32=0x20, PaymentMeans, for the instance with EID {eid}...")
        get_response = beacon_manager.send_get_request(eid, attrIdList=[0x20])
        root_logger.info(f"GET.response decoded: {get_response}")

    eid = 3
    # Operator auth key is optional, it is set to 111 by default
    root_logger.info(f"Sending a presentation request to EID {eid}")
    response = beacon_manager.presentation_request(eid, True, [0], 111)
    
    attribute_list_start_index = 10
    #attribute_list = custom_der_decoders.decode_attributes_list(response, attribute_list_start_index)
    #root_logger.debug(f"AttributeList in hex: {attribute_list}")

    root_logger.info(f"Sending a GET request on EID {eid} for attribute 16, the LPN")
    get_response = beacon_manager.send_get_request(eid, True, [16])
    root_logger.info(f"T-APDU containing a GET.response: {get_response}")

    if get_response['get-response']['ret'] == 0:
        lpn_value = beacon_manager.last_response_t_apdu_value[1]['attributelist'][0]['attributeValue'][1]
        EFC.EfcDataDictionary.Lpn.set_val(lpn_value)
        root_logger.debug(f"LPN value: {EFC.EfcDataDictionary.Lpn._val}")
        root_logger.debug(f"LPN in JER: {EFC.EfcDataDictionary.Lpn.to_jer()}")
        root_logger.debug(f"LPN in JSON: {EFC.EfcDataDictionary.Lpn._to_jval()}")
        root_logger.debug(f"LPN in ASN1 representation: {EFC.EfcDataDictionary.Lpn.to_asn1()}")
    else:
        root_logger.error("ReturnStatus is different from 0!!!")
    
    # CARDME transaction required attributes
    #root_logger.debug(f"Sending a GET request on EID {eid} for multiple attributes at once")
    cardme_attribute_list = [0, 16, 17, 20, 26, 33, 34]
    viapass_attribute_list = [0, 16, 17, 20]
    attribute_list = viapass_attribute_list
    root_logger.info(f"Sending a GET request on EID {eid} for attributes {attribute_list}")
    get_response = beacon_manager.send_get_request(eid, True, attribute_list)
    root_logger.info(f"GET.response decoded: {get_response}")
    
    root_logger.debug(f"Sending a GET_STAMPED request on EID {eid} for attribute 32, the PaymenMeans")
    get_stamped_response_json = beacon_manager.presentation_request(eid, True, [32])
    root_logger.info(f"GET_STAMPED.response in JSON: {get_stamped_response_json}")

    beacon_manager.verify_obe_authenticity()

    root_logger.debug("We should send a SetMMI command on the main Thread to close the transaction")
    root_logger.debug("Otherwise, the transaction will remain unclosed and cause an error on the next execution")
    set_mmi_reponse = beacon_manager.set_mmi(close=True)
    root_logger.debug(f"SetMMI response: {set_mmi_reponse}")
    # root_logger.info(f"VST: {json.dumps(t_apdu_with_vst, indent=2)}")

# Main execution
if __name__ == "__main__":
    main_thread = threading.Thread(target=main)
    main_thread.start()