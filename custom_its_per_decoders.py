# from ASN.compiled_DSRC_instances import LACv2_1 as EFC_CCC_LAC_asn1_objs
from ASN.compiled_DSRC_instances import AXXESv1_2 as EFC_CCC_LAC_asn1_objs
import baudot
import logging
import io

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

def decode_country_code(country_code:str) -> str:
    if type(country_code) is int:
        return decode_country_code_from_int(country_code)
    return decode_country_code_from_hex_str(country_code)

def decode_country_code_from_int(country_code_with_lsb_to_right_int:int) -> str:
    baudot_stream = split_country_code_baudot_chars_in_bytes(country_code_with_lsb_to_right_int)
    
    # ITA2_SWITCH_CODE: 0x1F
    code = bytes([0x1F]) + baudot_stream
    with io.BytesIO(code) as country_code_bitstream:
        reader = BaudotMsbFirstBytesReader(country_code_bitstream)
        alpha2 = baudot.decode_to_str(reader, baudot.codecs.ITA2_STANDARD)
    return alpha2

def decode_country_code_from_hex_str(country_code_with_msb_to_left_hex_str:str) -> str:
    country_code_12_bits = country_code_with_msb_to_left_hex_str[0:3]
    country_code_with_lsb_to_right_int = int(country_code_12_bits, 16) >> 2
    return decode_country_code_from_int(country_code_with_lsb_to_right_int)

custom_per_decoders_logger = logging.getLogger()
def decode_vst_parameter_oct_str_bytes(parameter_bytes):
    custom_per_decoders_logger.debug("Decoding VST Parameter bytes...")
    parameter_size = len(parameter_bytes)
    if parameter_size == 16:
        efc_cm_uper_bytes = parameter_bytes[0:6]
        EFC_CCC_LAC_asn1_objs.EfcDataDictionary.EfcContextMark.from_uper(efc_cm_uper_bytes)
        custom_per_decoders_logger.debug(f"EFC-CM value: {EFC_CCC_LAC_asn1_objs.EfcDataDictionary.EfcContextMark._val}")

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
        EFC_CCC_LAC_asn1_objs.EfcDataDictionary.EfcContextMark.from_uper(efc_cm_uper_bytes)
        custom_per_decoders_logger.debug(f"EFC-CM value: {EFC_CCC_LAC_asn1_objs.EfcDataDictionary.EfcContextMark._val}")
        decoded_vst_parameter = {
            "EFC-ContextMark": efc_cm_uper_bytes.hex(),
            }
    # Kapsch System Element: EID 0, no VST parameter
    elif parameter_size == 0:
        return {}
    else:
        raise Exception(f"Invalid Parameter length {parameter_size} in VST!!")
    custom_per_decoders_logger.debug(f"Decoded VST Parameter value: {decoded_vst_parameter}")
    return decoded_vst_parameter