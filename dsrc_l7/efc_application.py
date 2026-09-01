import time
import logging
import itertools


from ..toll_charging_security import tc_manage_toll_domains

from axxes_asn_compiles.ASN.compiled_DSRC_instances import AXXESv1_2
EFCv5 = AXXESv1_2

from . import dsrc_transactions
from .dsrc_l7_rse import RseDsrcL7App, build_and_init_rse_app, AbortedInitPhase
from .dsrc_l7_rse import UnclosedTransactionException

dsrc_l7_transactions_logger = logging.getLogger(__name__)

class AbortedTransaction(Exception):
    pass

class EfcApp():
    def __init__(self, rse_app) -> None:
        if type(rse_app) is not RseDsrcL7App:
            raise ValueError("Pass a RseDsrcL7App instance to constructor!!")
        self.rse_app = rse_app

    async def execute_transaction(self, transaction_name:str, *args, **kwargs):
        transaction_func = dsrc_transactions.DSRC_TRANSACTION_REGISTRY[transaction_name]
        await transaction_func(self.rse_app, *args, **kwargs)

    async def td_default_transaction(self, set_mmi=True):
        current_td = tc_manage_toll_domains.get_current_toll_domain()

        await dsrc_transactions.tc_single_transaction(self.rse_app, set_mmi=set_mmi, td_name=current_td)

class EfcLoop():
    def __init__(self, rse_app:RseDsrcL7App, keep_looping=False, loop_set_mmi_bool=False) -> None:
        if type(rse_app) is not RseDsrcL7App:
            raise ValueError("Pass a RseDsrcL7App instance to constructor!!")

        self.rse_app              = rse_app
        self.keep_looping         = keep_looping
        self.loop_set_mmi_bool    = loop_set_mmi_bool

    def stop_loop(self):
        self.keep_looping = False

    def set_beeping_state(self, beep_state=False):
        self.loop_set_mmi_bool = beep_state

    async def td_default_transaction(self, set_mmi=True):
        current_td = tc_manage_toll_domains.get_current_toll_domain()

        await dsrc_transactions.tc_single_transaction(self.rse_app, set_mmi=set_mmi, td_name=current_td)

    async def loop_transactions(self , beep_state=None):
        global keep_looping
        global loop_set_mmi_bool

        if beep_state is not None:
            self.set_beeping_state(beep_state=beep_state)

        if self.keep_looping == True:
            dsrc_l7_transactions_logger.error('Loop already in progress!!')
            return
        self.keep_looping = True
        if 'loop_set_mmi_bool' not in globals():
            loop_set_mmi_bool = False

        while self.keep_looping:
            try:
                await dsrc_transactions.get_attributes_in_list(self.rse_app, eid=4, attrIdList=[32], mand_applications=[1, 20], set_mmi=loop_set_mmi_bool)
                time.sleep(0.3)

                await dsrc_transactions.get_attributes_in_list(self.rse_app, eid=2, attrIdList=[16, 17, 18, 19, 20, 22, 32], mand_applications=[1, 20], set_mmi=False)
                time.sleep(0.01)
                await dsrc_transactions.get_attributes_in_list(self.rse_app, eid=2, attrIdList=[50, 51, 52], mand_applications=[1, 20], set_mmi=False)
                await dsrc_transactions.get_attributes_in_list(self.rse_app, eid=2, attrIdList=[53, 99, 100, 101], mand_applications=[1, 20], set_mmi=False)
                time.sleep(0.3)

                await dsrc_transactions.get_attributes_in_list(self.rse_app, eid=3, attrIdList=[16, 17, 18, 19, 20, 22, 32], mand_applications=[1, 20])
                time.sleep(0.01)
                await dsrc_transactions.get_attributes_in_list(self.rse_app, eid=3, attrIdList=[50, 51, 52], mand_applications=[1, 20], set_mmi=False)
                await dsrc_transactions.get_attributes_in_list(self.rse_app, eid=3, attrIdList=[53, 99, 100, 101], mand_applications=[1, 20], set_mmi=False)
                time.sleep(0.3)

                time.sleep(3)
            except UnclosedTransactionException:
                keep_looping = False
                dsrc_l7_transactions_logger.error("Transaction error occurred during loop!", exc_info=True)
                time.sleep(1)

    async def loop_transactions_on_toll_domains(self, beep_state=None, td_list=['TIS', 'DE', 'CH', 'BE'], sleep_time=3.0):
        global loop_set_mmi_bool
        td_list_cycle = itertools.cycle(td_list)

        if beep_state is not None:
            self.set_beeping_state(beep_state=beep_state)

        while True:
            try:
                current_td = next(td_list_cycle)
                print(current_td)
                # Change Toll Domain
                tc_manage_toll_domains.set_toll_domain(current_td)

                # Execute default transaction for the current Toll Domain
                try:
                    try:
                        await self.td_default_transaction(set_mmi=loop_set_mmi_bool)
                    except AbortedInitPhase as exc:
                        dsrc_l7_transactions_logger.warning('Timeout: No VST obtained!!')
                except AbortedTransaction as exc:
                    dsrc_l7_transactions_logger.error('Aborted transaction due to lack of a valid EFC-CM!!', exc_info=True)

                # Sleep between transactions
                time.sleep(sleep_time)
            except UnclosedTransactionException:
                keep_looping = False
                dsrc_l7_transactions_logger.error("Transaction error occurred during loop!", exc_info=True)
                time.sleep(1)

    async def loop_transactions_with_default_td_and_extra_tds(self, beep_state:bool|None=None, extra_td_list=['TIS'], sleep_time=3.0):
        if beep_state is not None:
            self.set_beeping_state(beep_state=beep_state)

        # Reset TD list on each iteration, since the Default TD name can be updated!!
        while True:
            default_td_name = tc_manage_toll_domains.get_current_toll_domain()
            td_list = [default_td_name, *extra_td_list]
            td_list_cycle = itertools.cycle(td_list)

            try:
                for current_td in td_list:
                    print(current_td)
                    # Change Toll Domain
                    tc_manage_toll_domains.set_toll_domain(current_td)

                    # Execute default transaction for the current Toll Domain
                    try:
                        try:
                            await self.td_default_transaction(set_mmi=loop_set_mmi_bool)
                        except AbortedInitPhase as exc:
                            print('Timeout: No VST obtained!!')
                    except AbortedTransaction as exc:
                        print(repr(exc))

                    # Sleep between transactions
                    time.sleep(sleep_time)
            except UnclosedTransactionException:
                keep_looping = False
                dsrc_l7_transactions_logger.error("Transaction error occurred during loop!", exc_info=True)
                time.sleep(1)

def build_efc_app(beacon_name:str, aid:int):
    rse_app = build_and_init_rse_app(beacon_name, aid)
    return EfcApp(rse_app)

def build_efc_loop_app(beacon_name:str, aid:int):
    rse_app = build_and_init_rse_app(beacon_name, aid)
    return EfcLoop(rse_app)
