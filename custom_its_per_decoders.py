from ASN.compiled_DSRC_instances import AXXESv1_2 as efc_asn_compilation
import baudot
import logging
import io

custom_per_decoders_logger = logging.getLogger(__name__)

# DEPRECATED
def decode_get_response_param(response_t_apdu_value):
    custom_per_decoders_logger.debug("We now obtain the GET_STAMPED.response object from the T_APDU response!")
    custom_per_decoders_logger.debug("GET_STAMPED.response is a parameterized type, so we cannot encode/decode it, only the T_APDU!")

    custom_per_decoders_logger.debug("We now obtain the GetStampedRq object in the ACTION.Response's parameter!")
    custom_per_decoders_logger.debug("GET_STAMPED.response is a parameterized type, so we cannot encode/decode it, only the T_APDU!")

    action_response_parameter = response_t_apdu_value[1]['responseParameter']
    get_stamped_response_value = action_response_parameter[1]
    custom_per_decoders_logger.info(f'GetStampedRq value: {get_stamped_response_value}')

    custom_per_decoders_logger.debug(f"GET_STAMPED.response (Presentation response): {response_t_apdu_value['actionResponse']['responseParameter']}")

    return get_stamped_response_value

def split_country_code_baudot_chars_in_bytes(country_code:int) -> bytes:
    first_5bits = (country_code >> 5) & 0b11111
    second_5bits = country_code & 0b11111
    return bytes([first_5bits, second_5bits])

def reverse_mask_5_bits(x:int) -> int:
    x = ((x & 0x05) << 1) | ((x & 0x0A) >> 1) | (x & 0x10)
    x = ((x & 0x03) << 2) | ((x & 0x0C) >> 2) | (x & 0x10)
    x = ((x & 0x0F) << 1) | ((x & 0x10) >> 4)
    return x

class ReadError(Exception):
     pass
class BaudotMsbFirstBytesReader(baudot.handlers.core.BaudotReader):
    def __init__(self, stream: io.BufferedIOBase):
        self.stream = stream

    def __next__(self):
        next_byte = self.stream.read(1)
        if not next_byte:
            raise StopIteration()
        try:
            code = next_byte[0]
            code = reverse_mask_5_bits(code)
        except ValueError:
            str_repr = next_byte.decode(errors='backslashreplace')
            raise ReadError(f'Invalid hexadecimal byte: {str_repr}')
        if not 0 <= code < 32:
            raise ReadError(f'Code value {code} is not a valid 5-bit value')
        # print(code)
        return code

# We can also use a dictionary with hardcoded values for the mapping:
# Baudot (ITA2 character set/alphabet with LSB on right) encoding of the ISO3166 Alpha2 Country Code (as an integer, hex or binary string...) >
# ISO3166 Numeric-3 Country Code (as an integer)
# Exampli Gratia: For France, FR = 714 (or even "2CA" or "B28") would be mapped to 250.
# I suggest to keep 2 dictionaries, one with the Baudot ITA2 Alpha2 > Numeric-3, and another with Alpha2 > Baudot ITA2 Alpha2 (or vice-versa)
# No need to keep a config for inverse mappings/dicts: Inverting a dict with unique values is simple.
# It is best to configure only the direct mappings and derive the inverses from them!
# Duplicating configs "for safety" only complicate things further and is way more unsafe!!!
def decode_baudot_country_code(baudot_country_code:str|int) -> str:
    if type(baudot_country_code) is int:
        return decode_baudot_country_code_from_int(baudot_country_code)
    if  type(baudot_country_code) is str:
        return decode_baudot_country_code_from_hex_str(baudot_country_code)
    else:
        raise TypeError("country_code must be either 'str' or 'int'!!")

def decode_baudot_country_code_from_int(baudot_country_code_with_lsb_to_right_int:int) -> str:
    baudot_stream = split_country_code_baudot_chars_in_bytes(baudot_country_code_with_lsb_to_right_int)
    
    # ITA2_SWITCH_CODE: 0x1F
    code = bytes([0x1F]) + baudot_stream
    with io.BytesIO(code) as country_code_bitstream:
        reader = BaudotMsbFirstBytesReader(country_code_bitstream)
        alpha2_country_code = baudot.decode_to_str(reader, baudot.codecs.ITA2_STANDARD)
    return alpha2_country_code

def decode_baudot_country_code_from_hex_str(baudot_country_code_with_msb_to_left_hex_str:str) -> str:
    baudot_country_code_12_bits = baudot_country_code_with_msb_to_left_hex_str[0:3]
    baudot_country_code_with_lsb_to_right_int = int(baudot_country_code_12_bits, 16) >> 2
    return decode_baudot_country_code_from_int(baudot_country_code_with_lsb_to_right_int)

class NoCardmeAppPresentInVst(Exception):
    pass
# Get EFC-CM, RndOBE and AC_CR-KeyRef values from any VST app with CARDME support!
# If no CARDME-compliant app is present, no AC_CR-KeyRef and RndOBE will be found...
def vst_decode_eid_efc_cm_rnd_obe_and_ac_cr_from_any_cardme_app_in_vst(vst_value:dict) -> tuple[int, bytes, int, int]:
    for application_data in vst_value['applications']:
        eid = application_data['eid']
        try:
            vst_app_param = application_data['parameter'][1]
            if len(vst_app_param) == 16:
                # Length 16: CARDME!! This VST Parameter contains AC_CR-KeyRef and RndOBE values!
                return eid, *decode_efc_cm_rnd_obe_and_ac_cr_from_cardme_app_param(vst_app_param)
        except KeyError:
            # VST app without parameter, lookup next...
            continue
    raise NoCardmeAppPresentInVst('VST does not have any CARDME applications!')

class EidNotFound(Exception):
    pass
class VstAppNotCardme(Exception):
    pass
def vst_decode_efc_cm_rnd_obe_and_ac_cr_from_cardme_app_in_vst_with_eid(eid:int, vst_value:dict) -> tuple[bytes, int, int]:
    for application_data in vst_value['applications']:
        if eid == application_data['eid']:
            try:
                vst_app_param = application_data['parameter'][1]
                if len(vst_app_param) == 16:
                    # Length 16: CARDME!! This VST Parameter contains AC_CR-KeyRef and RndOBE values!
                    return decode_efc_cm_rnd_obe_and_ac_cr_from_cardme_app_param(vst_app_param)
            except:
                raise VstAppNotCardme(f'VST app with EID {eid} is not a CARDME application!')
    raise EidNotFound(f'EID {eid} not found in VST!')

class NotCardmeVstParam(Exception):
    pass
def decode_efc_cm_rnd_obe_and_ac_cr_from_cardme_app_param(vst_app_param:bytes) -> tuple[bytes, int, int]:
    if len(vst_app_param) != 16:
        raise NotCardmeVstParam('CARDME VST Parameter must have length 16!!!')

    efc_cm_uper_bytes = vst_app_param[0:6]
    try:
        efc_asn_compilation.EfcDataDictionary.EfcContextMark.from_uper(vst_app_param[0:6])
    except efc_asn_compilation.ASN1ObjErr:
        custom_per_decoders_logger.error('Error when decode EFC-CM in VST!', exc_info=True)
        raise NotCardmeVstParam('Invalid EFC-CM in CARDME app!')

    if vst_app_param[6:8] != b'\x02\x02':
        raise NotCardmeVstParam('AC_CR should be a OCTET STRING of length 2!')
    ac_cr_key_ref = int.from_bytes(vst_app_param[8:10], "big")

    if vst_app_param[10:12] != b'\x02\x04':
        raise NotCardmeVstParam('RndOBE should be a OCTET STRING of length 4!')
    rnd_obe = int.from_bytes(vst_app_param[12:16], 'big')

    return efc_cm_uper_bytes, ac_cr_key_ref, rnd_obe

def decode_vst_parameter_oct_str_bytes(parameter_bytes):
    custom_per_decoders_logger.debug("Decoding VST Parameter bytes...")
    parameter_size = len(parameter_bytes)
    if parameter_size == 16:
        efc_cm_uper_bytes = parameter_bytes[0:6]
        efc_asn_compilation.EfcDataDictionary.EfcContextMark.from_uper(efc_cm_uper_bytes)
        custom_per_decoders_logger.debug(f"EFC-CM value: {efc_asn_compilation.EfcDataDictionary.EfcContextMark._val}")

        if parameter_bytes[6:8] != b"\x02\x02":
            raise Exception("Incorrect container choice and size for AC_CR-Reference!!")
        ac_cr_reference = int.from_bytes(parameter_bytes[8:10], "big")
        if parameter_bytes[10:12] != b"\x02\x04":
            raise Exception("Incorrect container choice and size for RndOBE!!")
        rnd_obe = int.from_bytes(parameter_bytes[12:16], 'big')
        decoded_vst_parameter = {
            "EFC-ContextMark": efc_cm_uper_bytes.hex().upper(),
            "AC_CR-KeyReference": ac_cr_reference,
            "RndOBE": rnd_obe
            }
    elif parameter_size == 6:
        efc_cm_uper_bytes = parameter_bytes[0:6]
        efc_asn_compilation.EfcDataDictionary.EfcContextMark.from_uper(efc_cm_uper_bytes)
        custom_per_decoders_logger.debug(f"EFC-CM value: {efc_asn_compilation.EfcDataDictionary.EfcContextMark._val}")
        decoded_vst_parameter = {
            "EFC-ContextMark": efc_cm_uper_bytes.hex(),
            }
    # Kapsch System Element: EID 0, no VST parameter
    elif parameter_size == 0:
        return {}
    else:
        raise Exception(f"Invalid Parameter length {parameter_size} in VST!!")
    custom_per_decoders_logger.info(f"Decoded VST Parameter value: {decoded_vst_parameter}")
    return decoded_vst_parameter

def decode_jer_dsrc_wgs_84_lat_long(signed_lat_long_int:int) -> str:
    # signed_lat_long_int += 2 << 30
    signed_lat_long_int += 2**31

    # print(f'LatLong joined int: {signed_lat_long_int}')
    # Horrible 8 decimal chars encoding/decoding...
    lat_long_joined_str = f"{signed_lat_long_int:08d}"
    # print(f'LatLong joined padded int str: {lat_long_joined_str}')

    before_decimal_point = lat_long_joined_str[:2]
    after_decimal_point = lat_long_joined_str[2:]
    lat_long_float_str = before_decimal_point + '.' + after_decimal_point
    # print(f'LatLong float str: {lat_long_float_str}')

    return lat_long_float_str

def decode_jer_dsrc_wgs_84_position(gnss_status_json):
    longitude_float = decode_jer_dsrc_wgs_84_lat_long(gnss_status_json['lastGnssFixLon'])
    latitude_float = decode_jer_dsrc_wgs_84_lat_long(gnss_status_json['lastGnssFixLat'])
    return [latitude_float, longitude_float]