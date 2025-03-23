import os
try:
    os.environ['MK_PATH']
except:
    os.environ['MK_PATH'] = r"..\master_keys_v1.1.0.json"

import asyncio

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from dsrc_l7 import dsrc_l7_rse

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

async def simple_bcm_transactions():
    await dsrc_l7_rse.init_bcm_and_set_transparent_mode()

    dsrc_l7_rse.set_beeping_state(beep_state=True)
    await dsrc_l7_rse.cardme_transaction(1, mand_applications=[1, 20, 29])

# Main execution
if __name__ == "__main__":
    asyncio.run(simple_bcm_transactions())