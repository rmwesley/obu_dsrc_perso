import logging
import time
import datetime as dt

decoder_logger = logging.getLogger(__name__)

def encode_date_compact(datetime_timestamp):
    return (datetime_timestamp.year - 1990 << 9) | (datetime_timestamp.month << 5) | (datetime_timestamp.day)
def encode_time_compact(datetime_timestamp):
    return (datetime_timestamp.hour << 11) | (datetime_timestamp.minute << 5) | (datetime_timestamp.second // 2)
def encode_date_and_time(utc_timestamp=None) -> int:
    if utc_timestamp is None:
        utc_timestamp = time.time()
    datetime_timestamp = dt.datetime.fromtimestamp(utc_timestamp)
    date_and_time = encode_date_compact(datetime_timestamp) << 16 | encode_time_compact(datetime_timestamp)
    return date_and_time

def decode_date_and_time(date_and_time):
    double_secs = date_and_time & 0b11111
    mins = date_and_time & (0b111111 < 5)
    hours = date_and_time & (0b11111 < 11)
    days = date_and_time & (0b11111 < 16)
    months = date_and_time & (0b1111 < 21)
    years = date_and_time & (0b1111111 < 25)

    return dt.datetime(1990 + years, months, days, hours, mins, 2*double_secs)


def decode_vst(vst_bytes, logger=decoder_logger):
    vst_data = {}
    decoder_logger.debug("Decoding VST...")
    decoder_logger.debug(vst_bytes.hex().upper())

    profile = vst_bytes[2]
    number_of_applications = vst_bytes[3]
    vst_byte_idx = 4

    decoder_logger.debug(f"\nProfile: {profile}")
    decoder_logger.debug(f"Number of applications: {number_of_applications}")

    applications = []
    # We now iterate over the applications (AID/EID pairs)...
    for aid_index in range(0, number_of_applications):
        current_application_details = {}

        decoder_logger.debug(f"Application {aid_index+1}:")

        eid_present = vst_bytes[vst_byte_idx] >> 7
        parameter_present = (vst_bytes[vst_byte_idx] >> 6) & 0x01

        # AID is 5 bits
        aid = vst_bytes[vst_byte_idx] & 0x1F
        current_application_details["AID"] = aid

        if aid == 1:
            decoder_logger.debug(f"\tAID: {aid} (EFC)")
        elif aid == 20:
            decoder_logger.debug(f"\tAID: {aid} (CCC)")
        elif aid == 29:
            decoder_logger.debug(f"\tAID: {aid} (UNI)")
        else:
            decoder_logger.debug(f"\tAID: {aid}")
        vst_byte_idx += 1

        if eid_present:
            eid = vst_bytes[vst_byte_idx]
            decoder_logger.debug(f"\tEID: {eid}")
            current_application_details["EID"] = eid
            vst_byte_idx += 1
        else:
            decoder_logger.debug(f"\tEID not present")
        if parameter_present:
            # Parameter/container here is always 2, for an octet string, EFC-CM
            # So the next 2 bytes are 0x02LL, the container type and size of the string
            # If size is 6, it is just an EFC-CM
            # If the size is 16 it contains access credentials
            container_type = vst_bytes[vst_byte_idx]
            container_length = vst_bytes[vst_byte_idx+1]
            decoder_logger.debug(f"\tContainer details: {bytes([container_type, container_length]).hex()}")

            if vst_bytes[vst_byte_idx] == 2:
                decoder_logger.debug(f"Container type (ASN1 tag) is {vst_bytes[vst_byte_idx]} for an Octet String")
            else :
                decoder_logger.error(f"Container type (ASN1 tag) is {container_type} instead of 02!!!")
    
            if container_length == 6:
                decoder_logger.debug(f"Length of Octet String is {container_length}, so we expect an EFC-CM only")
            elif container_length == 16:
                decoder_logger.debug(f"Length of Octet String is {container_length}, so we expect an EFC-CM with AC_CR-Reference right after the EFC-CM!")
            else:
                decoder_logger.error(f"Length of Octet String is {container_length}, which should never happen in a VST parameter")
            vst_byte_idx += 2

            # And then we get the actual EFC-CM:
            efc_cm_hex_str = bytes(vst_bytes[vst_byte_idx : vst_byte_idx + 3]).hex().upper()
            decoder_logger.debug(f"\tEFC-CM: {efc_cm_hex_str}")
            current_application_details["EFC-CM"] = efc_cm_hex_str

            # Country code is encoded in 10 bits
            country_code = (vst_bytes[vst_byte_idx] << 2) + (vst_bytes[vst_byte_idx] >> 6)
            # Issuer identifier is encoded in 14 bits
            issuer_id = ((vst_bytes[vst_byte_idx] & 0x3F) << 8) + vst_bytes[vst_byte_idx+1]

            vst_byte_idx += 3

            # We now get the TOC and CV
            toc = (vst_bytes[vst_byte_idx] << 8) + vst_bytes[vst_byte_idx+1]
            cv = vst_bytes[vst_byte_idx+2]

            decoder_logger.debug(f"\tTOC: {toc:04X}")
            decoder_logger.debug(f"\tCV: {cv}")
            vst_byte_idx += 3
        else:
            decoder_logger.debug(f"\tEFC-CM not present")
        
        # If the length of the parameter container in the application in the VST is 16, we have access credentials in it
        if container_length == 16:
            #decoder_logger.debug(f"\tApplication contains AC_CR-Reference, aka AC_CR-KeyReference!")
            # Getting Access Credentials data
            container_type = vst_bytes[vst_byte_idx]
            container_length = vst_bytes[vst_byte_idx+1]
            if container_type != 2 or container_length != 2:
                decoder_logger.error(f"\tAccess Credentials KeyRef container is {container_type:02X}{container_length:02X} instead of 0202")
            vst_byte_idx += 2

            #decoder_logger.debug("\tObtaining AC_CR-KeyRef details and keeping it as an int...")
            # Storing AC_CR-KeyRef as an int
            ac_cr_key_ref = int.from_bytes(vst_bytes[vst_byte_idx : vst_byte_idx+2], byteorder='big')
            decoder_logger.debug(f"AC_CR-KeyRef value in hex: {ac_cr_key_ref:04X}")
            current_application_details["AC_CR-KeyRef"] = ac_cr_key_ref

            vst_byte_idx += 2

            container_type = vst_bytes[vst_byte_idx]
            container_length = vst_bytes[vst_byte_idx+1]
            if container_type != 2 or container_length != 4:
                decoder_logger.error(f"\tRndOBE container is {container_type:02X}{container_length:02X} instead of 0204")
            vst_byte_idx += 2

            rnd_obe = bytes(vst_bytes[vst_byte_idx : vst_byte_idx+4])
            current_application_details["RndOBE"] = rnd_obe

            decoder_logger.debug(f"\tRndOBE: {rnd_obe.hex().upper()}")
            vst_byte_idx += 4

        applications.append(current_application_details)
    vst_data["applications"] = applications

    obe_status_present = vst_bytes[vst_byte_idx] & 0x80
    equipment_class = vst_bytes[vst_byte_idx] & 0x7F
    obe_manufacturer_id = vst_bytes[vst_byte_idx+1:vst_byte_idx+3]

    decoder_logger.debug(f"\tEquipment class: {equipment_class}")
    decoder_logger.debug(f"\tOBE manufacturerId: {int.from_bytes(obe_manufacturer_id)}")
    vst_byte_idx += 1

    if obe_status_present:
        obe_status = vst_bytes[vst_byte_idx]

    return vst_data