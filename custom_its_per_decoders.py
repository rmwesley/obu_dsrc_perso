from ASN.compiled_DSRC_instances import EFCv10_1 as EFC

import logging

custom_per_decoders_logger = logging.getLogger()
def decode_vst_parameter_oct_str_bytes(parameter_bytes):
    custom_per_decoders_logger.debug("Decoding VST Parameter bytes...")
    parameter_size = len(parameter_bytes)
    if parameter_size == 16:
        efc_cm_uper_bytes = parameter_bytes[0:6]
        EFC.EfcDataDictionary.EfcContextMark.from_uper(efc_cm_uper_bytes)
        custom_per_decoders_logger.debug(f"EFC-CM value: {EFC.EfcDataDictionary.EfcContextMark._val}")

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
        EFC.EfcDataDictionary.EfcContextMark.from_uper(efc_cm_uper_bytes)
        custom_per_decoders_logger.debug(f"EFC-CM value: {EFC.EfcDataDictionary.EfcContextMark._val}")
        decoded_vst_parameter = {
            "EFC-ContextMark": efc_cm_uper_bytes.hex(),
            }
    else:
        raise Exception(f"Invalid Parameter length {parameter_size} in VST!!")
    custom_per_decoders_logger.debug(f"Decoded VST Parameter value: {decoded_vst_parameter}")
    return decoded_vst_parameter