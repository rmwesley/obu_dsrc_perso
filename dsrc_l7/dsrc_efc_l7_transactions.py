import time
import logging
import json
import itertools

from dsrc_l7 import dsrc_l7_rse
from dsrc_security import dsrc_contracts, tc_manage_toll_domains

from ASN.compiled_DSRC_instances import AXXESv1_2
EFCv5 = AXXESv1_2
from ASN.compiled_DSRC_instances import CCCv1

dsrc_l7_transactions_logger = logging.getLogger(__name__)

class AbortedTransaction(Exception):
    pass

with open('settings/toll_domain_config.json') as json_file:
    toll_domain_config = json.load(json_file)

async def get_eid_in_vst_with_valid_contract_else_abort_transaction(vst_value: dict):
    try:
        return dsrc_contracts.get_eid_in_vst_with_valid_contract_in_current_td(vst_value=vst_value)
    except dsrc_contracts.NoValidObeEfcmFoundInVst as exc:
        dsrc_l7_transactions_logger.info(f'Aborting transaction due to no valid EFC-CM in VST: {vst_value}')
        await dsrc_l7_rse.send_close_transaction_echo()
        raise AbortedTransaction('No valid EFC-CM!!')

async def cardme_transaction(force_eid=None, mand_applications=[1, 20, 29], accessCredentialsPresent=False, set_mmi=True):
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(vst_value=last_vst_value)
    if force_eid is not None:
        eid = force_eid
    # Getting payment info!! (Core part)
    await dsrc_l7_rse.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    # Getting Receipt data...
    # dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[33, 34])

    # Getting contract information...
    # dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[4])

    # Getting Vehicle attributes...
    ## Getting LPN only first case errors occurs in the 'big' GET.request
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[17, 18, 19, 20, 22])

    # Getting OBE info...
    # dsrc_l7_rse.send_get_request(eid, False, attrIdList=[24, 25, 26])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24]) # Get equOBUId

    # Getting driver info...
    # dsrc_l7_rse.send_get_request(eid, False, attrIdList=[27, 47])

    # Close the transaction
    if set_mmi == True:
        await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)
    else:
        await dsrc_l7_rse.send_close_transaction_echo(eid=eid)

async def tis_vl_transaction(force_eid=None, mand_applications=[1, 20, 29], accessCredentialsPresent=False, set_mmi=True):
    """
    Used in the context of TIS VL CIP CARDME/Liber-t transactions.
    TIS: Télépéage Inter Sociétés
    CIP: Commission Interautoroutes Péage
    VL: Véhicule Léger
    """
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(vst_value=last_vst_value)
    if force_eid is not None:
        eid = force_eid
    await dsrc_l7_rse.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[17, 18, 19, 20, 22])

    # Getting TIS specific/reserved attributes...
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[125, 126])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[95, 96])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[97, 98, 99])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=list(range(100, 104)))
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=list(range(104, 108)))
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=list(range(108, 112)))
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=list(range(112, 116)))
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)
    else:
        await dsrc_l7_rse.send_close_transaction_echo(eid=eid)

async def test_ccc_2009_transaction(force_eid=None, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    global efc_asn_compilation
    # Compiled CCC 2015 specs
    efc_asn_compilation = CCCv1

    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(vst_value=last_vst_value)
    if force_eid is not None:
        eid = force_eid
    await dsrc_l7_rse.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # OBU ID
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC 2009 attributes...
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[48])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[49])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[50])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[51])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[52])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)
    else:
        await dsrc_l7_rse.send_close_transaction_echo(eid=eid)
    efc_asn_compilation = AXXESv1_2

async def test_ccc_2009_transaction_old(force_eid=None, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    global efc_asn_compilation
    # Compiled CCC 2015 specs
    efc_asn_compilation = CCCv1

    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(vst_value=last_vst_value)
    if force_eid is not None:
        eid = force_eid
    await dsrc_l7_rse.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # OBU ID
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC 2009 attributes...
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[37])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[38])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[39])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[40])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[41])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[42])

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)
    else:
        await dsrc_l7_rse.send_close_transaction_echo(eid=eid)
    efc_asn_compilation = AXXESv1_2

async def ccc_2015_status_history_transaction(force_eid=None, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    global efc_asn_compilation
    # Compiled CCC 2015 specs
    efc_asn_compilation = EFCv5

    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(vst_value=last_vst_value)
    if force_eid is not None:
        eid = force_eid
    await dsrc_l7_rse.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    # OBU ID
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC attributes...
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[55])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[60])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[61])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[62])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[63])

    # Close the transaction
    if set_mmi == True:
        await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)
    else:
        await dsrc_l7_rse.send_close_transaction_echo(eid=eid)
    efc_asn_compilation = AXXESv1_2

async def test_ccc_2015_transaction(force_eid=None, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    global efc_asn_compilation
    # Compiled CCC 2015 specs
    efc_asn_compilation = EFCv5

    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(vst_value=last_vst_value)
    if force_eid is not None:
        eid = force_eid
    await dsrc_l7_rse.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # Get OBU ID
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC attributes...
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[46])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[48])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[49])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[50])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[51])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[52])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[55])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[60])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[61])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[62])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[63])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[64])

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])

    # Close the transaction
    if set_mmi == True:
        await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)
    else:
        await dsrc_l7_rse.send_close_transaction_echo(eid=eid)
    efc_asn_compilation = AXXESv1_2

async def ccc_2023_transaction(force_eid=None, mand_applications=[1, 20, 29], accessCredentialsPresent=True, set_mmi=True):
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=mand_applications)
    eid = await get_eid_in_vst_with_valid_contract_else_abort_transaction(vst_value=last_vst_value)
    if force_eid is not None:
        eid = force_eid

    await dsrc_l7_rse.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # Get OBU ID
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[24])

    # Getting CCC attributes...
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[50])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[99])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[100])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[101])

    # Close the transaction
    if set_mmi == True:
        await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)
    else:
        await dsrc_l7_rse.send_close_transaction_echo(eid=eid)

async def kapsch_system_element_transaction(force_eid=0, mand_applications=[0], accessCredentialsPresent=True, set_mmi=True):
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=mand_applications)
    if force_eid is not None:
        eid = force_eid

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[1, 2, 3])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[6, 7])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[10])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[17])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[18])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[23])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[33])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[108])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[120])

    # Close the transaction
    if set_mmi == True:
        await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)
    else:
        await dsrc_l7_rse.send_close_transaction_echo(eid=eid)

async def test_transaction(force_eid=None, mand_applications=[1, 20, 29], accessCredentialsPresent=False, set_mmi=True):
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=mand_applications)
    if force_eid is not None:
        eid = force_eid

    await dsrc_l7_rse.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16, 17, 18, 19, 20, 22, 32])

    # Getting CCC attributes...
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[53])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[99])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[100])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[101])

    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[111, 115, 118])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[116])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[124])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[127])
    await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[125, 126])

    # Close the transaction
    if set_mmi == True:
        await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)
    else:
        await dsrc_l7_rse.send_close_transaction_echo(eid=eid)

async def get_all_attributes(eid, mand_applications=[1, 20, 29]):
    attrIdList = list(range(0, 128))
    return await get_attributes_in_list(eid, attrIdList, mand_applications=mand_applications)

async def get_attributes_in_list(eid, accessCredentialsPresent=True, attrIdList=[32], mand_applications=[1, 20, 29], set_mmi=False):
    global last_response_t_apdu_json

    # Initialize transaction
    _, last_vst_value = await dsrc_l7_rse.initialize_transaction(mand_applications=mand_applications)

    # Send GET.requests
    obtained_attrs = set()
    get_responses = []
    try:
        for attr in attrIdList:
            await dsrc_l7_rse.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[attr])
            try:
                if last_response_t_apdu_json['getResponse']['ret'] == 0:
                    dsrc_l7_transactions_logger.info(last_response_t_apdu_json['getResponse'])
                    obtained_attrs.add(attr)
                    get_responses.append(last_response_t_apdu_json['getResponse']['attributelist'])
            except KeyError:
                dsrc_l7_transactions_logger.info(last_response_t_apdu_json['getResponse'])
                obtained_attrs.add(attr)
                get_responses.append(last_response_t_apdu_json['getResponse']['attributelist'])
    except dsrc_l7_rse.EIDNotFoundException:
        dsrc_l7_transactions_logger.error("EID not present!", stack_info=True)
    dsrc_l7_transactions_logger.info(f"Obtained attributes: {obtained_attrs}")
    dsrc_l7_transactions_logger.info(f"Rejected attributes: {set(attrIdList).difference(obtained_attrs)}")

    # dsrc_l7_transactions_logger.info(json.dumps(get_responses, indent=2))

    # Close the transaction
    if set_mmi == True:
        await dsrc_l7_rse.send_close_transaction_setmmi(eid=eid)
    else:
        await dsrc_l7_rse.send_close_transaction_echo(eid=eid)

    return obtained_attrs, get_responses

def stop_loop():
    global keep_looping
    keep_looping = False

def set_beeping_state(beep_state=False):
    global loop_set_mmi_bool
    loop_set_mmi_bool = beep_state

def loop_transactions(beep_state=None):
    global keep_looping
    global loop_set_mmi_bool

    if beep_state is not None:
        set_beeping_state(beep_state=beep_state)

    if keep_looping == True:
        dsrc_l7_transactions_logger.error('Loop already in progress!!')
        return
    keep_looping = True
    if 'loop_set_mmi_bool' not in globals():
        loop_set_mmi_bool = False

    while keep_looping:
        try:
            get_attributes_in_list(eid=4, attrIdList=[32], mand_applications=[1, 20], set_mmi=loop_set_mmi_bool)
            time.sleep(0.3)

            get_attributes_in_list(eid=2, attrIdList=[16, 17, 18, 19, 20, 22, 32], mand_applications=[1, 20], set_mmi=False)
            time.sleep(0.01)
            get_attributes_in_list(eid=2, attrIdList=[50, 51, 52], mand_applications=[1, 20], set_mmi=False)
            get_attributes_in_list(eid=2, attrIdList=[53, 99, 100, 101], mand_applications=[1, 20], set_mmi=False)
            time.sleep(0.3)

            get_attributes_in_list(eid=3, attrIdList=[16, 17, 18, 19, 20, 22, 32], mand_applications=[1, 20])
            time.sleep(0.01)
            get_attributes_in_list(eid=3, attrIdList=[50, 51, 52], mand_applications=[1, 20], set_mmi=False)
            get_attributes_in_list(eid=3, attrIdList=[53, 99, 100, 101], mand_applications=[1, 20], set_mmi=False)
            time.sleep(0.3)

            time.sleep(3)
        except dsrc_l7_rse.UnclosedTransactionException:
            keep_looping = False
            dsrc_l7_transactions_logger.error("Transaction error occurred during loop!", exc_info=True)
            time.sleep(1)

async def td_default_transaction(set_mmi=True):
    current_td = tc_manage_toll_domains.current_toll_domain_name

    transaction_type = toll_domain_config['td_conf_by_td_name'][current_td]['default_transaction_type']
    default_mand_applications = toll_domain_config['td_conf_by_td_name'][current_td]['mandApplications']
    accessCredentialsPresent = tc_manage_toll_domains.td_is_en15509_level_1()
    if transaction_type == 'CARDME':
        await cardme_transaction(mand_applications=default_mand_applications, accessCredentialsPresent=accessCredentialsPresent, set_mmi=set_mmi)
    elif transaction_type == 'PISTA':
        await cardme_transaction(mand_applications=default_mand_applications, accessCredentialsPresent=accessCredentialsPresent, set_mmi=set_mmi)
    elif transaction_type == 'CCC2009':
        await test_ccc_2009_transaction(mand_applications=default_mand_applications, accessCredentialsPresent=accessCredentialsPresent, set_mmi=set_mmi)
    elif transaction_type == 'CCC2015':
        await test_ccc_2015_transaction(mand_applications=default_mand_applications, accessCredentialsPresent=accessCredentialsPresent, set_mmi=set_mmi)
    elif transaction_type == 'CCC2019':
        await ccc_2023_transaction(mand_applications=default_mand_applications, accessCredentialsPresent=accessCredentialsPresent, set_mmi=set_mmi)
    elif transaction_type == 'CCC2023':
        await ccc_2023_transaction(mand_applications=default_mand_applications, accessCredentialsPresent=accessCredentialsPresent, set_mmi=set_mmi)

async def loop_transactions_on_toll_domains(beep_state=None, td_list=['TIS', 'DE', 'CH', 'BE'], sleep_time=3.0):
    global loop_set_mmi_bool
    td_list_cycle = itertools.cycle(td_list)

    if beep_state is not None:
        set_beeping_state(beep_state=beep_state)

    while True:
        try:
            current_td = next(td_list_cycle)
            print(current_td)
            # Change Toll Domain
            tc_manage_toll_domains.set_toll_domain(current_td)

            # Execute default transaction for the current Toll Domain
            try:
                try:
                    await td_default_transaction(set_mmi=loop_set_mmi_bool)
                except dsrc_l7_rse.AbortedInitPhase as exc:
                    dsrc_l7_transactions_logger.warning('Timeout: No VST obtained!!')
            except AbortedTransaction as exc:
                dsrc_l7_transactions_logger.error('Aborted transaction due to lack of a valid EFC-CM!!', exc_info=True)

            # Sleep between transactions
            time.sleep(sleep_time)
        except dsrc_l7_rse.UnclosedTransactionException:
            keep_looping = False
            dsrc_l7_transactions_logger.error("Transaction error occurred during loop!", exc_info=True)
            time.sleep(1)

async def loop_transactions_with_default_td_and_extra_tds(beep_state=None, extra_td_list=['TIS'], sleep_time=3.0):
    global loop_set_mmi_bool

    if beep_state is not None:
        set_beeping_state(beep_state=beep_state)

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
                        await td_default_transaction(set_mmi=loop_set_mmi_bool)
                    except dsrc_l7_rse.AbortedInitPhase as exc:
                        print('Timeout: No VST obtained!!')
                except AbortedTransaction as exc:
                    print(repr(exc))

                # Sleep between transactions
                time.sleep(sleep_time)
        except dsrc_l7_rse.UnclosedTransactionException:
            keep_looping = False
            dsrc_l7_transactions_logger.error("Transaction error occurred during loop!", exc_info=True)
            time.sleep(1)