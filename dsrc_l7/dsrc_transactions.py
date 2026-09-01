import logging
import json
import asyncio
import pathlib
from typing import Protocol

from ..toll_charging_security import tc_dsrc_contracts, tc_manage_toll_domains

from axxes_asn_compiles.ASN.compiled_DSRC_instances import AXXESv1_2
EFCv5 = AXXESv1_2
from axxes_asn_compiles.ASN.compiled_DSRC_instances import CCCv1

from .dsrc_l7_rse import RseDsrcL7App, EIDNotFoundException

SLEEP_AFTER_ABORTING_TRANSACTION = 0.3
dsrc_l7_transactions_logger = logging.getLogger(__name__)

class AbortedTransaction(Exception):
    pass

package_root_dir = pathlib.Path(__file__).resolve().parent.parent
with (package_root_dir / 'settings/td_transaction_config.json' ).open() as json_file:
    td_transaction_config = json.load(json_file)

async def get_eid_in_vst_with_valid_contract_else_abort_transaction(rse_app:RseDsrcL7App, vst_value: dict):
    try:
        td_name = tc_manage_toll_domains.get_current_toll_domain()
        return tc_dsrc_contracts.get_eid_in_vst_with_valid_contract_in_td(vst_value=vst_value, td_name=td_name)
    except tc_dsrc_contracts.NoValidObeEfcmFoundInVst as exc:
        dsrc_l7_transactions_logger.info(f'Aborting transaction due to no valid EFC-CM in VST: {vst_value}')
        await rse_app.send_close_transaction_echo()
        await asyncio.sleep(SLEEP_AFTER_ABORTING_TRANSACTION)
        raise AbortedTransaction('No valid EFC-CM!!')

async def forced_cardme_transaction(rse_app:RseDsrcL7App, force_eid=None, mand_applications=[1, 20, 29], accessCredentialsPresent=False, set_mmi=True):
    _, last_vst_value = await rse_app.initialize_transaction(mand_applications=mand_applications)
    if not force_eid:
        raise ValueError('Forced EID must be set!')
    eid = force_eid

    # Getting payment info!! (Core part)
    await rse_app.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    # Getting Receipt data...
    # rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[33, 34])

    # Getting contract information...
    # rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[4])

    # Getting Vehicle attributes...
    ## Getting LPN only first case errors occurs in the 'big' GET.request
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[17, 18, 19, 20, 22])

    # Getting OBE info...
    # rse_app.send_get_request(eid, False, attrIdList=[24, 25, 26])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24]) # Get equOBUId

    # Getting driver info...
    # rse_app.send_get_request(eid, False, attrIdList=[27, 47])

    # Close the transaction
    if set_mmi == True:
        await rse_app.send_close_transaction_setmmi(eid=eid)
    else:
        await rse_app.send_close_transaction_echo(eid=eid)

async def test_transaction(rse_app:RseDsrcL7App, force_eid=1, mand_applications=[1, 20, 29], accessCredentialsPresent=False, set_mmi=True):
    _, last_vst_value = await rse_app.initialize_transaction(mand_applications=mand_applications)
    if force_eid is not None:
        eid = force_eid

    await rse_app.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # Getting CCC attributes...
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[99])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[100])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[101])

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[111, 115, 118])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[125, 126])

    # Close the transaction
    if set_mmi == True:
        await rse_app.send_close_transaction_setmmi(eid=eid)
    else:
        await rse_app.send_close_transaction_echo(eid=eid)

async def get_attributes_in_list(rse_app:RseDsrcL7App, eid, attrIdList=[32], mand_applications=[1, 20, 29], accessCredentialsPresent=False, set_mmi=False):
    # Initialize transaction
    _, last_vst_value = await rse_app.initialize_transaction(mand_applications=mand_applications)

    # Send GET.requests
    obtained_attrs = set()
    get_responses = []
    try:
        for attr in attrIdList:
            await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[attr])
            if not rse_app.last_rs_t_apdu_val:
                raise RuntimeError("T-APDU data was lost!!!")
            try:
                if rse_app.last_rs_t_apdu_val['getResponse']['ret'] == 0:
                    dsrc_l7_transactions_logger.info(rse_app.last_rs_t_apdu_val['getResponse'])
                    obtained_attrs.add(attr)
                    get_responses.append(rse_app.last_rs_t_apdu_val['getResponse']['attributelist'])
            except KeyError:
                dsrc_l7_transactions_logger.info(rse_app.last_rs_t_apdu_val['getResponse'])
                obtained_attrs.add(attr)
                get_responses.append(rse_app.last_rs_t_apdu_val['getResponse']['attributelist'])
    except EIDNotFoundException:
        dsrc_l7_transactions_logger.error("EID not present!", stack_info=True)
    dsrc_l7_transactions_logger.info(f"Obtained attributes: {obtained_attrs}")
    dsrc_l7_transactions_logger.info(f"Rejected attributes: {set(attrIdList).difference(obtained_attrs)}")

    # dsrc_l7_transactions_logger.info(json.dumps(get_responses, indent=2))

    # Close the transaction
    if set_mmi == True:
        await rse_app.send_close_transaction_setmmi(eid=eid)
    else:
        await rse_app.send_close_transaction_echo(eid=eid)

    return obtained_attrs, get_responses

async def get_all_attributes(eid, mand_applications=[1, 20, 29], accessCredentialsPresent=False, set_mmi=False):
    attrIdList = list(range(0, 128))
    return await get_attributes_in_list(eid, attrIdList, mand_applications=mand_applications)

async def tc_single_transaction(rse_app:RseDsrcL7App, set_mmi=True, td_name='TIS'):
    tc_manage_toll_domains.set_toll_domain(td_name)

    transaction_func_name = td_transaction_config['td_conf_by_td_name'][td_name]['default_transaction_type']
    default_mand_applications = td_transaction_config['td_conf_by_td_name'][td_name]['mandApplications']
    accessCredentialsPresent = tc_manage_toll_domains.td_is_en15509_level_1()

    transaction_func = DSRC_TRANSACTION_REGISTRY[transaction_func_name]
    await transaction_func(rse_app, default_mand_applications, accessCredentialsPresent, set_mmi)

class TransactionFunc(Protocol):
    async def __call__(self,
        rse_app:RseDsrcL7App,
        mand_applications:list=[1, 20, 29],
        accessCredentialsPresent:bool=False,
        set_mmi:bool=False
    ):
        ...

DSRC_TRANSACTION_REGISTRY:dict[str, TransactionFunc] = {}
def dsrc_transaction(name):
    def decorator(func):
        DSRC_TRANSACTION_REGISTRY[name] = func
        return func
    return decorator

@dsrc_transaction("pista_transaction")
@dsrc_transaction("cardme_transaction")
async def cardme_transaction(rse_app:RseDsrcL7App, mand_applications=[1, 20, 29], accessCredentialsPresent=False, set_mmi=True):
    _, last_vst_value = await rse_app.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(rse_app, vst_value=last_vst_value)

    # Getting payment info!! (Core part)
    await rse_app.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    # Getting Receipt data...
    # rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[33, 34])

    # Getting contract information...
    # rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[4])

    # Getting Vehicle attributes...
    ## Getting LPN only first case errors occurs in the 'big' GET.request
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[17, 18, 19, 20, 22])

    # Getting OBE info...
    # rse_app.send_get_request(eid, False, attrIdList=[24, 25, 26])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24]) # Get equOBUId

    # Getting driver info...
    # rse_app.send_get_request(eid, False, attrIdList=[27, 47])

    # Close the transaction
    if set_mmi == True:
        await rse_app.send_close_transaction_setmmi(eid=eid)
    else:
        await rse_app.send_close_transaction_echo(eid=eid)

@dsrc_transaction("tis_vl_transaction")
async def tis_vl_transaction(rse_app:RseDsrcL7App, mand_applications=[1, 20, 29], accessCredentialsPresent=False, set_mmi=True):
    """
    Used in the context of TIS VL CIP CARDME/Liber-t transactions.
    TIS: Télépéage Inter Sociétés
    CIP: Commission Interautoroutes Péage
    VL: Véhicule Léger
    """
    _, last_vst_value = await rse_app.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(rse_app, vst_value=last_vst_value)

    await rse_app.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[17, 18, 19, 20, 22])

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24]) # Get equOBUId

    # Getting TIS specific/reserved attributes...
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[125, 126])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[95, 96])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[97, 98, 99])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=list(range(100, 104)))
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=list(range(104, 108)))
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=list(range(108, 112)))
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=list(range(112, 116)))
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await rse_app.send_close_transaction_setmmi(eid=eid)
    else:
        await rse_app.send_close_transaction_echo(eid=eid)

@dsrc_transaction("test_ccc_2009_transaction")
async def test_ccc_2009_transaction(rse_app:RseDsrcL7App, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    global efc_asn_compilation
    # Compiled CCC 2015 specs
    efc_asn_compilation = CCCv1

    _, last_vst_value = await rse_app.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(rse_app, vst_value=last_vst_value)

    await rse_app.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # OBU ID
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC 2009 attributes...
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[48])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[49])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[50])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[51])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[52])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await rse_app.send_close_transaction_setmmi(eid=eid)
    else:
        await rse_app.send_close_transaction_echo(eid=eid)
    efc_asn_compilation = AXXESv1_2

@dsrc_transaction("test_ccc_2009_transaction_old")
async def test_ccc_2009_transaction_old(rse_app:RseDsrcL7App, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    global efc_asn_compilation
    # Compiled CCC 2015 specs
    efc_asn_compilation = CCCv1

    _, last_vst_value = await rse_app.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(rse_app, vst_value=last_vst_value)

    await rse_app.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # OBU ID
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC 2009 attributes...
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[37])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[38])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[39])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[40])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[41])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[42])

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await rse_app.send_close_transaction_setmmi(eid=eid)
    else:
        await rse_app.send_close_transaction_echo(eid=eid)
    efc_asn_compilation = AXXESv1_2

@dsrc_transaction("ccc_2015_status_history_transaction")
async def ccc_2015_status_history_transaction(rse_app:RseDsrcL7App, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    global efc_asn_compilation
    # Compiled CCC 2015 specs
    efc_asn_compilation = EFCv5

    _, last_vst_value = await rse_app.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(rse_app, vst_value=last_vst_value)

    await rse_app.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    # OBU ID
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC attributes...
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[55])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[60])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[61])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[62])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[63])

    # Close the transaction
    if set_mmi == True:
        await rse_app.send_close_transaction_setmmi(eid=eid)
    else:
        await rse_app.send_close_transaction_echo(eid=eid)
    efc_asn_compilation = AXXESv1_2

@dsrc_transaction("test_ccc_2015_transaction")
async def test_ccc_2015_transaction(rse_app:RseDsrcL7App, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    global efc_asn_compilation
    # Compiled CCC 2015 specs
    efc_asn_compilation = EFCv5

    _, last_vst_value = await rse_app.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(rse_app, vst_value=last_vst_value)

    await rse_app.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # Get OBU ID
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC attributes...
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[46])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[48])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[49])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[50])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[51])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[52])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[55])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[60])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[61])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[62])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[63])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[64])

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await rse_app.send_close_transaction_setmmi(eid=eid)
    else:
        await rse_app.send_close_transaction_echo(eid=eid)
    efc_asn_compilation = AXXESv1_2

@dsrc_transaction("ccc_2023_transaction")
async def ccc_2023_transaction(rse_app:RseDsrcL7App, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    _, last_vst_value = await rse_app.initialize_transaction(mand_applications=mand_applications)

    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(rse_app, vst_value=last_vst_value)

    await rse_app.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # Get OBU ID
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC attributes...
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[50])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[52])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[99])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[100])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[101])

    # Close the transaction
    if set_mmi == True:
        await rse_app.send_close_transaction_setmmi(eid=eid)
    else:
        await rse_app.send_close_transaction_echo(eid=eid)

@dsrc_transaction("ccc_2024_transaction")
async def ccc_2024_transaction(rse_app:RseDsrcL7App, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    _, last_vst_value = await rse_app.initialize_transaction(mand_applications=mand_applications)

    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(rse_app, vst_value=last_vst_value)

    await rse_app.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # Get OBU ID
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC attributes...
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[50])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[52])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[63])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[99])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[100])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[101])

    # Close the transaction
    if set_mmi == True:
        await rse_app.send_close_transaction_setmmi(eid=eid)
    else:
        await rse_app.send_close_transaction_echo(eid=eid)

@dsrc_transaction("kapsch_system_element_transaction")
async def kapsch_system_element_transaction(rse_app:RseDsrcL7App, mand_applications=[0], accessCredentialsPresent=True, set_mmi=True):
    _, last_vst_value = await rse_app.initialize_transaction(mand_applications=mand_applications)
    eid=0

    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[1, 2, 3])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[6, 7])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[10])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[17])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[18])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[23])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[33])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[108])
    await rse_app.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[120])

    # Close the transaction
    if set_mmi == True:
        await rse_app.send_close_transaction_setmmi(eid=eid)
    else:
        await rse_app.send_close_transaction_echo(eid=eid)

def resolve_transaction_profile(toll_domain: str, script_name: str = 'default', runtime_config: dict | None = None, compiled_spec_name: str | None = None) -> dict:
    runtime_config = runtime_config or {}
    td_conf = td_transaction_config['td_conf_by_td_name'].get(toll_domain, {})
    transaction_type = td_conf.get('default_transaction_type', 'CARDME')
    security_profile = td_conf.get('security_profile', '')
    mand_applications = td_conf.get('mandApplications', [1])

    preferred_script = (script_name or 'default').strip().lower()
    script_aliases = {
        'default': 'cardme_transaction',
        'cardme': 'cardme_transaction',
        'tis_vl': 'tis_vl_transaction',
        'ccc2009': 'test_ccc_2009_transaction',
        'ccc2015': 'test_ccc_2015_transaction',
        'ccc2023': 'ccc_2023_transaction',
        'ccc2024': 'ccc_2024_transaction',
        'test': 'test_transaction',
    }

    transaction_type_to_handler = {
        'CARDME': 'cardme_transaction',
        'TIS_CIP_CARDME': 'tis_vl_transaction',
        'PISTA': 'cardme_transaction',
        'CCC2009': 'test_ccc_2009_transaction',
        'CCC2015': 'test_ccc_2015_transaction',
        'CCC2019': 'ccc_2023_transaction',
        'CCC2023': 'ccc_2023_transaction',
        'CCC2024': 'ccc_2024_transaction',
    }

    handler_name = script_aliases.get(preferred_script)
    if handler_name is None:
        handler_name = transaction_type_to_handler.get(transaction_type, 'cardme_transaction')

    access_credentials_present = runtime_config.get('accessCredentialsPresent')
    if access_credentials_present is None:
        access_credentials_present = 'EN15509_level_1' in security_profile

    return {
        'resolved_toll_domain': toll_domain,
        'selected_script': script_name or 'default',
        'transaction_type': transaction_type,
        'handler_name': handler_name,
        'mand_applications': mand_applications,
        'accessCredentialsPresent': access_credentials_present,
        'set_mmi': runtime_config.get('set_mmi', True),
        'security_profile': security_profile,
        'compiled_spec_name': compiled_spec_name,
    }

async def execute_resolved_transaction_profile(
    rse_app:RseDsrcL7App,
    toll_domain: str,
    script_name: str = "default",
    runtime_config: dict | None = None,
    compiled_spec_name: str | None = None,
):
    runtime_config = runtime_config or {}

    profile = resolve_transaction_profile(
        toll_domain=toll_domain,
        script_name=script_name,
        runtime_config=runtime_config,
        compiled_spec_name=compiled_spec_name,
    )

    handler_name = profile["handler_name"]

    try:
        handler = DSRC_TRANSACTION_REGISTRY[handler_name]
    except KeyError:
        raise ValueError(
            f"Unsupported transaction handler '{handler_name}'"
        )

    result = await handler(
        rse_app,
        mand_applications=profile["mand_applications"],
        accessCredentialsPresent=profile["accessCredentialsPresent"],
        set_mmi=profile["set_mmi"],
    )

    return {
        "completed": True,
        "handler": handler_name,
        "transaction_type": profile["transaction_type"],
        "toll_domain": profile["resolved_toll_domain"],
        "compiled_spec_name": compiled_spec_name,
        "result": result,
    }

def activate_compiled_spec(compiled_module):
    efc_asn_compilation = compiled_module
