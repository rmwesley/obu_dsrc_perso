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
    GRAY = "\033[38;20m"
    YELLOW = "\033[33;20m"
    RED = "\033[31;20m"
    BOLD_RED = "\033[31;1m"
    RESET_COLOR = "\033[0m"
    default_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)")
    formatter = None

    LEVEL_COLORS = {
        logging.DEBUG: GRAY,
        logging.INFO: GRAY,
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
    beacon_manager.start_bst(0x00D0, 0xBA00, [0x01])
    
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
    response = beacon_manager.get_request(eid, attribute_id_list=[0x20])
    root_logger.debug(f"BCM last command response in hex format: {beacon_manager.last_cmd_response.hex().upper()}")

    eid = 7
    # IssuerId = ContractProvider = EFC-CM
    issuer_id = vst_data['applications'][1]['EFC-CM']

    root_logger.debug(f"AC_CR-KeyRef in hex: {vst_data["AC_CR-KeyRef"]:04X}")
    #ac_cr_mk_ref = vst_data["AC_CR-Ref"]["AC_CR-MasterKeyRef"]
    #ac_cr_diversifier = vst_data["AC_CR-Ref"]["AC_CR-Diversifier"]
    #root_logger.debug(f"AC_CR-MasterKeyReference in hex: {ac_cr_mack_ref:02X}")
    #root_logger.debug(f"AC_CR-Diversifier in hex: {ac_cr_diversifier:02X}")
    ac_cr_key_ref = vst_data["AC_CR-KeyRef"]

    rnd_obe = vst_data["RndOBE"]
    access_credentials = key_derivation.compute_access_credentials(issuer_id, rnd_obe, ac_cr_key_ref)
    root_logger.debug(f"Generated Access Credentials in hex format: {access_credentials:08X}")

    # Operator auth key is optional, we set it to 111 by default
    #chosen_auth_key = 111
    #beacon_manager.presentation_request(eid, access_credentials, chosen_auth_key)
    beacon_manager.presentation_request(eid, access_credentials)


    root_logger.debug("We should send a SetMMI command on the main Thread to close the transaction")
    root_logger.debug("Otherwise, the transaction will remain unclosed and cause an error on the next execution")
    beacon_manager.set_mmi(True)


# Main execution
if __name__ == "__main__":
    main_thread = threading.Thread(target=main)
    main_thread.start()
