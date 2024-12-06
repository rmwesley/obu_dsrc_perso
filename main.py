import os
import re
import time
import json

try:
    os.environ['MK_PATH']
except:
    os.environ['MK_PATH'] = r"..\master_keys.json"

import threading
import logging
import dsrc_security

from datetime import datetime

from ASN.compiled_DSRC_instances import LACv2_1 as EFC_CCC_LAC_asn1_objs

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from gea_bcm_dll_wrapper import *
# from beacon_manager_class import BeaconManager
import beacon_manager_module

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

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
date_prefix = datetime.now().strftime('%y%m%d')
file_handler = logging.FileHandler(f'main_logs/{date_prefix}_gea_bcm_dll_python_wrapper.log')
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
    beacon_manager_module.initialize_bcm()

    root_logger.debug("Getting beacon configuration...")
    bcm_config = beacon_manager_module.beacon_l7_wrapper.get_config()
    root_logger.debug(f"Displaying config data...: {bcm_config}")
    
    beacon_manager_module.beacon_l7_wrapper.change_mode(BCM_MODE_Enum.BCM_MOD_Transparent)
    root_logger.debug("Changed mode to transparent!")
    
    root_logger.debug("Getting beacon state...")
    result = beacon_manager_module.beacon_l7_wrapper.update_state()

    root_logger.debug("We now update/get the BeaconID (L7, so according to the beacon) before sending the BST")
    root_logger.debug("This is weird... We should be the ones to set the BeaconID freely in the BST")
    root_logger.debug("The beacon should then just keep the last sent BeaconID in its memory")
    result = beacon_manager_module.beacon_l7_wrapper.update_beacon_id()
    EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.BeaconID.from_uper(beacon_manager_module.beacon_l7_wrapper.last_beacon_id)
    root_logger.debug(f"Beacon (according to GEA Beacon) encoded in JER: {EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.BeaconID.to_jer()}")

    root_logger.debug("Initialization: Starting BST and getting VST...")

    # Requesting EFC, CCC and UNI
    required_applications = [1, 20, 29]
    root_logger.info(f"Preparing a BST requesting AIDs {required_applications}")

    beacon_manager_module.loop_transactions()

# Main execution
if __name__ == "__main__":
    main_thread = threading.Thread(target=main)
    main_thread.start()