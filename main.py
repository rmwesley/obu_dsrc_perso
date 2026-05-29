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

async def forced_cardme_transaction(force_eid=1):
    await dsrc_l7_rse.init_bcm_and_set_transparent_mode()
    dsrc_l7_rse.SKIP_CONTRACT_DSRC_AUTH = True

    await dsrc_efc_l7_transactions.forced_cardme_transaction(force_eid)

async def default_transaction():
    await dsrc_l7_rse.init_bcm_and_set_transparent_mode()

    await dsrc_efc_l7_transactions.td_default_transaction(set_mmi=True)

async def single_transaction(td_name='TIS'):
    await dsrc_l7_rse.init_bcm_and_set_transparent_mode()

    await dsrc_efc_l7_transactions.tc_single_transaction(set_mmi=True, td_name=td_name)

async def toll_domains_transaction_loop(td_list:list[str] = ['TIS', 'EasyGo', 'DE', 'CH', 'BE']):
    await dsrc_l7_rse.init_bcm_and_set_transparent_mode()

    await dsrc_efc_l7_transactions.loop_transactions_on_toll_domains(beep_state=True, td_list=td_list, sleep_time=5.0)

async def default_toll_domain_transaction_loop(extra_td_list:list[str] = ['TIS']):
    await dsrc_l7_rse.init_bcm_and_set_transparent_mode()

    await dsrc_efc_l7_transactions.loop_transactions_with_default_td_and_extra_tds(beep_state=True, extra_td_list=extra_td_list, sleep_time=5.0)

# Main execution
if __name__ == "__main__":
    # asyncio.run(default_toll_domain_transaction_loop(extra_td_list=['NL', 'BE', 'DE']))
    # asyncio.run(default_toll_domain_transaction_loop(extra_td_list=['EasyGo', 'VIA-T2']))
    # CCC
    # asyncio.run(toll_domains_transaction_loop(['CH', 'CEA', 'NL', 'BE', 'DE']))

    # EFC
    # # asyncio.run(forced_cardme_transaction(1))
    # asyncio.run(toll_domains_transaction_loop(td_list=['TIS', 'EasyGo', 'CH', 'BE']))
    # asyncio.run(default_transaction())

    asyncio.run(single_transaction('VIA-T2'))

    # asyncio.run(toll_domains_transaction_loop(['VIA-T2', 'TIS', 'IT_CEN', 'TIS_INCONNU']))

    # asyncio.run(toll_domains_transaction_loop(['NL', 'TIS', 'DE', 'CH', 'BE', 'VIA-T2', 'IT_CEN']))
    # asyncio.run(toll_domains_transaction_loop(['IT_CEN', 'TIS', 'NL', 'BE', 'DE']))
    # asyncio.run(toll_domains_transaction_loop(['TIS', 'IT_CEN', 'NL', 'BE', 'DE']))