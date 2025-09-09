
import json
import logging
import typing
import datetime

from dsrc_security import kapsch_http_uset_key_obtention, kapsch_uset_compute_ac_cr_locally

perso_secops_logger = logging.getLogger(__name__)
perso_secops_logger.setLevel(logging.DEBUG)

startup_date = datetime.datetime.now()
logs_date_prefix = startup_date.strftime('%y%m%d')

# SETTING UP LOGGER FILE HANDLER
file_handler = logging.FileHandler(f'logs/beacon_logs/{logs_date_prefix}_perso_secops.log')
file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)
perso_secops_logger.addHandler(file_handler)

uset_mkset_name_by_obu_model_and_key_type = {}
with open('../security_info/tsp_obu_setup/axxes_kapsch_uset_mkset_by_obu_model_v2.0.0.json', 'r') as json_file:
    uset_mkset_name_by_obu_model_and_key_type = json.load(json_file)

default_uset_key_type = 'Exploit'
KAPSCH_USET_MK_TYPES = typing.Literal['SystemElementAcK', 'Stock', 'Exploit']
def set_default_key_type(uset_key_type:KAPSCH_USET_MK_TYPES):
    global default_uset_key_type
    default_uset_key_type = uset_key_type

def compute_uset_derived_key_for_obu_model(obu_model:str, ac_cr_key_ref:int, uset_key_type=default_uset_key_type) -> bytes:
    if not uset_key_type:
        uset_key_type = default_uset_key_type
    return kapsch_http_uset_key_obtention.compute_uset_derived_key_for_obu_model(obu_model, ac_cr_key_ref, uset_key_type)

def decrypt_uset_derived_key_for_obu_model(obu_model:str, ciphertext:bytes, uset_key_type=default_uset_key_type) -> bytes:
    if not uset_key_type:
        uset_key_type = default_uset_key_type

    uset_mkset_name = uset_mkset_name_by_obu_model_and_key_type[obu_model]['uset_mk_info'][uset_key_type]

    return kapsch_http_uset_key_obtention.decrypt_uset_derived_key(uset_mkset_name=uset_mkset_name, ciphertext=ciphertext)

# This can be too slow for DSRC communication!
def compute_kapsch_uset_access_credentials_for_obu_model(obu_model:str, ac_cr_key_ref:int, rnd_obe:int, uset_key_type=default_uset_key_type) -> bytes:
    if uset_key_type is None:
        uset_key_type = default_uset_key_type

    return kapsch_http_uset_key_obtention.compute_kapsch_uset_access_credentials_for_obu_model(obu_model, ac_cr_key_ref, rnd_obe, uset_key_type)

# Compute AC_CR from the USET, that should be provided along with the OBU's personalization data, that is, before DSRC transaction phase starts!
# This should happen in the end of the initialization phase, after a VST with the OBU's AC_CR-KeyRef value is provided!
# That is, after VST, and before a GET_NONCE!
def compute_kapsch_uset_access_credentials_from_a_provided_uset(rnd_obe:int, derived_uset_key:bytes) -> bytes:
    return kapsch_uset_compute_ac_cr_locally.compute_access_credentials_with_uset_key(rnd_obe, derived_uset_key)

class InvalidObuModel(Exception):
    pass
def check_obu_model(expected_obu_eq_ref:str, obu_model:str):
    if expected_obu_eq_ref not in uset_mkset_name_by_obu_model_and_key_type[obu_model]['supported_obu_eq_refs']:
        raise InvalidObuModel(f'OBU with Manufacturer Id/Equipment Class 0x{expected_obu_eq_ref} is not of model {obu_model}')

# USET key update dict preparation function
def get_eid_and_new_uset_attribute_dict(eid:int, obu_model:str, ac_cr_key_ref:int, new_uset_key_type=default_uset_key_type) -> tuple[int, dict]:
    uset_key_info = uset_mkset_name_by_obu_model_and_key_type[obu_model]['dsrc_mem_key_locations'][eid]['uset_key']

    uset_key_eid = eid
    # USET key EID is normally the same EID, otherwise, the key is stored in another element.
    # This is a workaround used for TIS-VL EFC elements, since they use attribute IDs 111 through 118 for historization (D-HIS)!
    if 'external_eid' in uset_key_info:
        uset_key_eid = uset_key_info['external_eid']

    uset_key_attr_id = uset_key_info['storage_attr_id']
    uset_key_bytes = compute_uset_derived_key_for_obu_model(obu_model, ac_cr_key_ref, new_uset_key_type)

    # 0x02 = EfcContainer CHOICE tag for OCTET STRING
    uset_key_octet_string_uper_hex = f'02{len(uset_key_bytes):02X}{uset_key_bytes.hex().upper()}'
    new_uset_attr_dict = {
        uset_key_attr_id: uset_key_octet_string_uper_hex
    }
    return uset_key_eid, new_uset_attr_dict

# USET key update dict preparation function
def get_eid_and_new_uset_attribute_dict_generator_for_obu_model(obu_model:str, ac_cr_key_ref:int, new_uset_key_type=default_uset_key_type):
    for eid, eid_sec_info in uset_mkset_name_by_obu_model_and_key_type[obu_model]['dsrc_mem_key_locations'].items():
        if eid == 0:
            # We do not update/switch the Access/USET key for Kapsch's SystemElement (EID 0)!
            return

        if 'uset_key' not in eid_sec_info:
            perso_secops_logger.info(f'No USET keys for EID {eid} of OBU model {obu_model}!')
            continue
        uset_key_info = eid_sec_info['uset_key']

        uset_key_eid = int(eid)
        # USET key EID is normally the same EID, otherwise, the key is stored in another element.
        # This is a workaround used for TIS-VL EFC elements, since they use attribute IDs 111 through 118 for historization (D-HIS)!
        if 'external_eid' in uset_key_info:
            uset_key_eid = int(uset_key_info['external_eid'])

        uset_key_attr_id = int(uset_key_info['storage_attr_id'])
        uset_key_bytes = compute_uset_derived_key_for_obu_model(obu_model, ac_cr_key_ref, new_uset_key_type)

        # 0x02 = EfcContainer CHOICE tag for OCTET STRING
        uset_key_octet_string_uper_hex = f'02{len(uset_key_bytes):02X}{uset_key_bytes.hex().upper()}'
        new_uset_attr_dict = {
            uset_key_attr_id: uset_key_octet_string_uper_hex
        }
        perso_secops_logger.debug(f'USET info for EID {eid}: Key in EID {uset_key_eid}, on attributes {new_uset_attr_dict}')
        uset_key_storage_eid_and_attribute = {'uset_key_eid': uset_key_eid, 'attribute_dict': new_uset_attr_dict}
        yield (eid, uset_key_storage_eid_and_attribute)

# USET key update dict preparation function
def get_new_uset_attribute_dict_by_eid_for_obu_model(obu_model:str, ac_cr_key_ref:int, new_uset_key_type=default_uset_key_type):
    return dict(get_eid_and_new_uset_attribute_dict_generator_for_obu_model(obu_model, ac_cr_key_ref, new_uset_key_type))