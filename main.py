import asyncio

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from obu_dsrc_perso.dsrc_l7.efc_application import EfcApp, build_efc_app, EfcLoop, build_efc_loop_app
from obu_dsrc_perso.dsrc_l7.dsrc_transactions import tc_single_transaction

import logging

root_logger = logging.getLogger()

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
        color = ColoredFormatterWrapper.LEVEL_COLORS[record.levelno]
        if not self.formatter:
            raise ValueError("Undefined formatter!")

        colored_formatting = color + self.formatter.format(record) + ColoredFormatterWrapper.RESET_COLOR
        return colored_formatting
console_formatter = ColoredFormatterWrapper(logging.Formatter(f"%(levelname)-8s %(filename)22s:%(lineno)-4s - %(threadName)s: %(message)s"))
console_handler.setFormatter(console_formatter)
root_logger.addHandler(console_handler)
root_logger.setLevel(logging.WARNING)

async def forced_cardme_transaction(efc_app:EfcApp, force_eid=1):
    await efc_app.execute_transaction("forced_cardme_transaction", force_eid)

async def default_transaction(efc_app:EfcApp):
    await efc_app.td_default_transaction(set_mmi=False)

async def single_transaction(efc_app:EfcApp, td_name='TIS'):
    await tc_single_transaction(efc_app.rse_app, set_mmi=False, td_name=td_name)

async def toll_domains_transaction_loop(efc_loop:EfcLoop, td_list:list[str] = ['TIS', 'EasyGo', 'DE', 'CH', 'BE']):
    await efc_loop.loop_transactions_on_toll_domains(beep_state=False, td_list=td_list, sleep_time=5.0)

async def default_toll_domain_transaction_loop(efc_loop:EfcLoop, extra_td_list:list[str] = ['TIS']):
    await efc_loop.loop_transactions_with_default_td_and_extra_tds(beep_state=False, extra_td_list=extra_td_list, sleep_time=5.0)

# Main execution
if __name__ == "__main__":
    efc_app = build_efc_app("TGBV", aid=20)
    # efc_app.rse_app.SKIP_CONTRACT_DSRC_AUTH = True

    # efc_loop = build_efc_loop_app("TGBV", aid=20)

    # asyncio.run(default_toll_domain_transaction_loop(extra_td_list=['NL', 'BE', 'DE']))
    # asyncio.run(default_toll_domain_transaction_loop(extra_td_list=['EasyGo', 'VIA-T2']))
    # CCC
    # asyncio.run(toll_domains_transaction_loop(['CH', 'CEA', 'NL', 'BE', 'DE']))

    # EFC
    # # asyncio.run(forced_cardme_transaction(1))
    # asyncio.run(toll_domains_transaction_loop(td_list=['TIS', 'EasyGo', 'CH', 'BE']))
    # asyncio.run(default_transaction())

    asyncio.run(single_transaction(efc_app, 'TIS'))

    # asyncio.run(toll_domains_transaction_loop(['VIA-T2', 'TIS', 'IT_CEN', 'TIS_INCONNU']))

    # asyncio.run(toll_domains_transaction_loop(['NL', 'TIS', 'DE', 'CH', 'BE', 'VIA-T2', 'IT_CEN']))
    # asyncio.run(toll_domains_transaction_loop(['IT_CEN', 'TIS', 'NL', 'BE', 'DE']))
    # asyncio.run(toll_domains_transaction_loop(['TIS', 'IT_CEN', 'NL', 'BE', 'DE']))