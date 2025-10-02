import asyncio

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from dsrc_l7 import dsrc_efc_l7_transactions, dsrc_l7_rse

import logging

root_logger = logging.getLogger()
root_logger.setLevel(logging.WARNING)

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

    await dsrc_efc_l7_transactions.td_default_transaction(set_mmi=True)

async def toll_domains_transaction_loop(td_list:list[str] = ['TIS', 'EasyGo', 'DE', 'CH', 'BE']):
    await dsrc_l7_rse.init_bcm_and_set_transparent_mode()

    await dsrc_efc_l7_transactions.loop_transactions_on_toll_domains(beep_state=True, td_list=td_list, sleep_time=5.0)

async def default_toll_domain_transaction_loop(extra_td_list:list[str] = ['TIS']):
    await dsrc_l7_rse.init_bcm_and_set_transparent_mode()

    await dsrc_efc_l7_transactions.loop_transactions_with_default_td_and_extra_tds(beep_state=True, extra_td_list=extra_td_list, sleep_time=5.0)

# Main execution
if __name__ == "__main__":
    asyncio.run(default_toll_domain_transaction_loop(extra_td_list=['BE', 'CH', 'VIA-T2', 'IT_CEN', 'EasyGo', 'TIS']))