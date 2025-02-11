import os
import re
import time
import json

try:
    os.environ['MK_PATH']
except:
    os.environ['MK_PATH'] = r"..\master_keys_v1.1.0.json"

import threading

from ASN.compiled_DSRC_instances import LACv2_1 as EFC_CCC_LAC_asn1_objs

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from gea_bcm_dll_wrapper import *
import dsrc_security
import beacon_manager_module

import logging


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

def simple_bcm_transactions():
    beacon_manager_module.init_bcm_and_set_transparent_mode()

    beacon_manager_module.set_beeping_state(beep_state=False)
    beacon_manager_module.cardme_transaction(1, mand_applications=[1, 20, 29])
    # beacon_manager_module.tis_cip_cardme_transaction(eid=1, mand_applications=[1])
    # beacon_manager_module.ccc_transaction(eid=3)

    # beacon_manager_module.loop_transactions()

    # beacon_manager_module.test_transaction(eid=1, mand_applications=[1, 29], accessCredentialsPresent=True)
    # beacon_manager_module.kapsch_system_element_transaction(accessCredentialsPresent=True)

# Main execution
if __name__ == "__main__":
    beacon_thread = threading.Thread(target=simple_bcm_transactions, daemon=True)
    beacon_thread.start()

    while beacon_thread.is_alive:
        beacon_thread.join(1)