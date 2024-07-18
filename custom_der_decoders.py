import logging
import time
import datetime as dt

class ContainerType:
    INTEGER = 0
    OCTET_STRING = 2
    UNIVERSAL_STRING = 3
    BEACON_ID = 4
    T_APDU = 5
    DSRC_APPLICATION_ENTITY_ID = 6
    DSRC_ASE_ID = 7
    ATTR_ID_LIST = 8
    ATTR_LIST = 9
    BROADCAST_POOL = 10
    DIRECTORY = 11
    FILE = 12
    FILE_TYPE = 13
    RECORD = 14
    TIME = 15
    VECTOR = 16
    GSTRQ = 17
    GSTRS = 18
    SSTRQ = 19
    GINRQ = 20
    GINRS = 21
    SINRQ = 22
    CHARQ = 23
    CHARS = 24
    CPPRQ = 25
    SUBRQ = 26
    ADDRQ = 27
    DEBRQ = 28
    DEBRS = 29
    CRERQ = 30
    CRERS = 31
    EFC_CONTEXT_MARK = 32
    CONT_SER = 33
    CONT_VAL = 34
    CONT_VEH = 35
    CONTAUTH = 36
    REC_SPT = 37
    SESSIONCLS = 38
    RECSERVSERIALNO = 39
    REC_FINPT_ENV = 40
    REC_CONT = 41
    REC_OBU_ID = 42
    REC_ICC_ID = 43
    REC_TEXT = 44
    REC_AUTH = 45
    REC_DIST = 46
    VEHLPN = 47
    VEHID = 48
    VEHCLASS = 49
    VEHDIMS = 50
    VEHAXLES = 51
    VEHWTLIMS = 52
    VEHWTLADEN = 53
    VEHSPCHARS = 54
    VEHAUTH = 55
    EQU_OBU_ID = 56
    EQU_ICC_ID = 57
    EQU_STAT = 58
    DVRCHARS = 59
    PAYMEANS_ENV = 60
    PAYMBAL = 61
    PAYMUNIT = 62
    PAYSECDATA = 63
    PAYMEANS = 64
    RECDATA1 = 65
    RECDATA2 = 66
    VALOFCON = 67
    REC_FINPT = 68
    SETMMIRQ = 69
    AWL = 70
    PACA = 71
    ENG = 72
    SL = 73
    EEV = 74
    DEV = 75
    CO2EV = 76
    VTD = 77
    TLPN = 78
    TCH = 79
    ANP = 80
    RFUCENISO48 = 81
    RFUCENISO49 = 82
    RFUCENISO50 = 83
    RFUCENISO51 = 84
    RFUCENISO52 = 85
    RFUCENISO53 = 86
    # Container type values [87..127] are reserved for private EFC use and intended for the addressing of the corresponding private attribute identifiers.

FIXED_SIZE_CONTAINER_TYPE_SIZES = {
    ContainerType.EFC_CONTEXT_MARK: 6,
    ContainerType.CONT_SER: 4,
    ContainerType.CONT_VAL: 6,
    ContainerType.VALOFCON: 4,
    ContainerType.REC_SPT: 13,
    ContainerType.SESSIONCLS: 2,
    ContainerType.RECSERVSERIALNO: 3,
    ContainerType.REC_FINPT: 23,
    ContainerType.REC_CONT: 9,
    ContainerType.REC_DIST: 3,
    ContainerType.RECDATA1: 28,
    ContainerType.RECDATA2: 28,
    ContainerType.VEHCLASS: 1,
    ContainerType.VEHDIMS: 3,
    ContainerType.VEHAXLES: 2,
    ContainerType.VEHWTLIMS: 6,
    ContainerType.VEHWTLADEN: 2,
    ContainerType.VEHSPCHARS: 4,
    ContainerType.AWL: 10,
    ContainerType.PACA: 2,
    ContainerType.ENG: 4,
    ContainerType.SL: 2,
    ContainerType.EEV: 8,
    ContainerType.DEV: 4,
    ContainerType.CO2EV: 2,
    ContainerType.VTD: 4,
    ContainerType.EQU_STAT: 2,
    ContainerType.DVRCHARS: 2,
    ContainerType.ANP: 1,
    ContainerType.PAYMEANS: 14,
    ContainerType.PAYMBAL: 3,
    ContainerType.PAYMUNIT: 2,
}

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

class DSRC_Data_Container:
    def __init__(self, content: bytes):
        self.content = content
        self.content_type = content[0]

    def represent_lpn(self):
        vehicle_licence_plate_number = self.content
        country_code = bytes(vehicle_licence_plate_number[0 : 2]) >> 6
        lpn_length = vehicle_licence_plate_number[3]
        lpn_value = vehicle_licence_plate_number[4 : 4 + lpn_length].decode('utf-8')
        return {
            "country_code" : country_code,
            "lpn_length" : lpn_length,
            "lpn_value" : lpn_value,
        }
    def __repr__(self):
        if self.content_type == ContainerType.VEHLPN:
            return self.represent_lpn()
        else:
            return self.content.hex().upper()

def decode_attributes_list(datagram, attribute_list_start_index):
    datagram_index = attribute_list_start_index

    number_of_attributes_in_list = datagram[datagram_index]
    datagram_index += 1

    decoded_attribute_list = []
    while len(decoded_attribute_list) < number_of_attributes_in_list:
        attribute_id = datagram[datagram_index]

        # Container Choice or ContainerType
        container_type = datagram[datagram_index + 1]
        decoder_logger.debug(f"Decoding attribute with Container Type {container_type} = 0x{container_type:01X}")
        if container_type in FIXED_SIZE_CONTAINER_TYPE_SIZES:
            length = FIXED_SIZE_CONTAINER_TYPE_SIZES[container_type]
        else:
            length = datagram[datagram_index + 2]

        # Attribute value including its Container Type and optional Length, but without the AttributeId
        attribute_value = datagram[datagram_index + 1 : datagram_index + length + 3]
        datagram_index += length + 3

        attribute_value_bytes = bytes(attribute_value)
        decoder_logger.debug(f"Attribute value in hex: {attribute_value_bytes.hex().upper()}")
        attribute = {
            "attribute_id": attribute_id,
            "value": attribute_value_bytes.hex().upper(),
            "representation": DSRC_Data_Container(attribute_value_bytes).__repr__()
            }

        decoded_attribute_list.append(attribute)
    return decoded_attribute_list

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