import logging
import time
import datetime as dt

# CountryCode is encoded with ITA2 (or Baudot) encoding
import baudot
from io import BytesIO

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
    VEHICLE_LPN = 47
    VEHID = 48
    VEHICLE_CLASS = 49
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
    PAYMENT_MEANS_ENV = 60
    PAYMBAL = 61
    PAYMUNIT = 62
    PAYSECDATA = 63
    PAYMENT_MEANS = 64
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
    ContainerType.VEHICLE_CLASS: 1,
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
    ContainerType.PAYMENT_MEANS: 14,
    ContainerType.PAYMBAL: 3,
    ContainerType.PAYMUNIT: 2,
}


class ReturnStatus(Exception):
    noError = 0
    accessDenied = 1
    argumentError = 2
    complexityLimitation = 3
    processingFailure = 4
    processing = 5

    def __init__(self, value) -> None:
        self.value = value
        if value != ReturnStatus.noError:
            #decoder_logger.error(f"Error response received from OBE! Error code is {value} and error description is {self.get_description()}")
            decoder_logger.error(self.get_description())
    def get_description(self):
        #decoder_logger.debug(f"Getting description for ReturnStatus={self.value}")
        if self.value == ReturnStatus.noError:
            return "No Error!"
        if self.value == ReturnStatus.accessDenied:
            return "Access Denied!"
        if self.value == ReturnStatus.argumentError:
            return "Bad Request: Argument Error"
        if self.value == ReturnStatus.complexityLimitation:
            return "Complexity Limitation"
        if self.value == ReturnStatus.processingFailure:
            return "Processign Failure!"
        if self.value == ReturnStatus.processing:
            return "Processing..."
        return f"Unknown ReturnStatus value ({self.value})!"


decoder_logger = logging.getLogger(__name__)

def encode_date_compact(datetime_timestamp: dt.datetime):
    return (datetime_timestamp.year - 1990 << 9) | (datetime_timestamp.month << 5) | (datetime_timestamp.day)
def decode_date_compact(date_compact : int):
    decoder_logger.debug(f"Decoding date from hex {date_compact:X}")
    day = date_compact & 0b11111
    month = (date_compact >> 5) & 0b1111
    year = (date_compact >> 9) + 1990
    return f"{year:04d}-{month:02d}-{day:02d}"

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

def encode_country_code(country_code_bytes):
    country_code_int = int.from_bytes(country_code_bytes)

    # Each baudot (ITA2) character is encoded with 5 bits
    # As such, the country code is encoded in only 10 bits, so we remove 6 of its 16 bits
    first_5bits = (country_code_int >> 11) & 0b11111
    second_5bits = (country_code_int >> 6) & 0b11111
    
    # Now, we invert the bits
    first_letter_encoding = int('{:05b}'.format(first_5bits).zfill(5)[::-1], 2)
    second_letter_encoding = int('{:05b}'.format(second_5bits).zfill(5)[::-1], 2)
    # 0x1F is the header needed in the baudot decoder for some reason...
    country_code_5bits_pair = bytes([0x1F, first_letter_encoding, second_letter_encoding]).hex().encode('utf-8')

    # Reverse bit order (LSB should be on the right)
    with BytesIO(country_code_5bits_pair) as country_code_bitstream:
        reader = baudot.handlers.HexBytesReader(country_code_bitstream)
        country_code_str = baudot.decode_to_str(reader, baudot.codecs.ITA2_STANDARD)
    decoder_logger.debug(f"Country code to be decoded in decimal: {country_code_int}")

    return country_code_str

class DSRC_Data_Container:
    def __init__(self, content: bytes):
        self.content = content
        self.content_type = content[0]

    def represent_payment_means(self):
        pan_bytes = bytes(self.content[1 : 11])
        pm_expiry_date_bytes = int.from_bytes(bytes(self.content[11 : 13]))
        pm_usage_control = bytes(self.content[14 : 16])
        return {
            "type": "PaymentMeans",
            "PAN": pan_bytes.hex().upper(),
            "pm_expiry_date": decode_date_compact(pm_expiry_date_bytes),
            "pm_usage_contol": pm_usage_control.hex().upper()
        }

    def represent_lpn(self):
        # Country code is encoded in 10 bits only
        country_code_bytes = bytes(self.content[1 : 3])
        countr_code_str = encode_country_code(country_code_bytes)

        lpn_length = self.content[3]
        lpn_value = self.content[4 : 4 + lpn_length].decode('utf-8')
        return {
            "type": "LPN",
            "country_code" : countr_code_str,
            "lpn_length" : lpn_length,
            "lpn_value" : lpn_value,
        }
    def represent_efc_cm(self):
        efc_cm = self.content
        country_code = int.from_bytes(bytes(efc_cm[1 : 3])) >> 6
        issuer_id = int.from_bytes(bytes(efc_cm[2 : 4])) & 0x3FFF
        type_of_contract = bytes(efc_cm[4 : 6])
        context_version = efc_cm[6]

        return  {
            "type": "EFC-Context-Mark",
            "contract_provider" : {
                "type" : 'Provider',
                "country_code": country_code,
                "issuer_id": issuer_id
            },
            "type_of_contract": type_of_contract.hex().upper(),
            "context_version": context_version
        }
    def represent_as_dict(self):
        decoder_logger.debug(f"Representing {self.content.hex().upper()}")
        if self.content_type == ContainerType.VEHICLE_LPN:
            return self.represent_lpn()
        if self.content_type == ContainerType.PAYMENT_MEANS:
            return self.represent_payment_means()
        if self.content_type == ContainerType.EFC_CONTEXT_MARK:
            return self.represent_efc_cm()
        else:
            return self.content.hex().upper()
    def __repr__(self) -> str:
        return repr(self.represent_as_dict())

def decode_request(datagram):
    request_header = datagram[1] >> 4
    if request_header == 0b0111:
        decoder_logger.debug("Decoding a GET.response...")
        return None
    if request_header == 0b0000:
        decoder_logger.debug("Decoding an ACTION.request...")
        return None
    raise("Not a request datagram!!")

def decode_response(datagram):
    response_header = datagram[1] >> 4
    if response_header == 0b0111:
        decoder_logger.debug("Decoding a GET.response...")
        return decode_get_response(datagram)
    if response_header == 0b0001:
        decoder_logger.debug("Decoding an ACTION.response...")
        return decode_action_response(datagram)
    decoder_logger.error("Not a response datagram!!")

def decode_action_request(datagram):
    action_type = datagram[3] >> 4
    if action_type == 0:
        decoder_logger("Decoding a GET_STAMPED.request...")
        return None
    if action_type == 10:
        decoder_logger("Decoding a SET_MMI.request...")

def encode_get_request_datagram(frag_header, eid, access_credentials=None, attribute_ids=None, close = False):
    decoder_logger.debug(f"Preparing a GET.request to get attributes with ids {attribute_ids}")
    # 0b0110 0000 = 0x60
    get_req_header = 0x60
    if access_credentials:
        # Access Credentials are present!
        get_req_header = get_req_header | 0b1000
        # Length + Value
        ac_cr_list = [4] + list(access_credentials.to_bytes(4, 'big'))
    else:
        ac_cr_list = []
    
    if attribute_ids:
        # AttributeIdList is present!
        get_req_header = get_req_header | 0b10
        # Length + Value
        attribute_id_list = [len(attribute_ids)] + attribute_ids
    else:
        attribute_id_list = []
    
    get_request_datagram = [frag_header, get_req_header, eid] + ac_cr_list + attribute_id_list
    decoder_logger.debug(f"Get Request datalist: {get_request_datagram}")

    # Converting command request to bytes structure and returning it
    return bytes(get_request_datagram)

def decode_get_response(datagram):
    get_return_status_present = (datagram[1] >> 1) & 1
    eid = datagram[2]
    get_response = {"type": "GET.response"}

    return_status = None
    # Return Status is present
    if get_return_status_present != 0:
        # Return Status is present
        decoder_logger.debug(f"GET.response for the request sent to EID {eid} contains a ReturnStatus code!")

        return_status = ReturnStatus(datagram[3])
        get_response["ReturnStatus"] = return_status.value

        if return_status.value != 0:
            decoder_logger.error(f"ReturnStatus contains an error code ({return_status.value})!")
        return get_response
    
    attribute_list, size_in_bytes = decode_attributes_list(datagram, 3)
    get_response["AttributeList"] = attribute_list
    get_response['AttributeList_size'] = size_in_bytes

    return get_response

def decode_set_response(datagram):
    action_response_return_status_present = (datagram[1] >> 2) & 1
    eid = datagram[2]
    if action_response_return_status_present is not 0:
        return_status = ReturnStatus(datagram[3])

        #decoder_logger.error(return_status.get_description())
        decoder_logger.error(f"SET.response for the request sent to EID {eid} contains an error status!")
        #decoder_logger.debug(f"The error code is {return_status.value}")
        return {
            "type": "SET.response",
            "EID": eid,
            "ReturnStatus": return_status
        }
    return None

def decode_action_response(datagram):
    action_response_type = datagram[1] >> 4
    # Second bit from the right in second byte from the left informs whether a ReturnStatus is present
    action_response_return_status_present = (datagram[1] >> 1) & 1
    eid = datagram[2]


    if action_response_return_status_present is not 0:
        return_status = ReturnStatus(datagram[3])
        #decoder_logger.error(return_status.get_description())
        decoder_logger.error(f"Action.response for the request sent to EID {eid} contains an error status!")
        decoder_logger.debug(f"The error code (return status) is {return_status.value}")
        return
    if action_response_type == 1:
        decoder_logger.debug("Decoding a GET_STAMPED.response...")
        action_response = {"type": "GET_STAMPED.response"}
        action_response["ResponseParameter"] = {"type": "GetStampedRs"}

        attribute_list, size_in_bytes = decode_attributes_list(datagram, attribute_list_start_index=4)
        action_response["ResponseParameter"]["AttributeList"] = attribute_list
        action_response["ResponseParameter"]['AttributeList_size'] = size_in_bytes

        authenticator_index = 4 + size_in_bytes
        authenticator_length = datagram[authenticator_index]
        action_response["ResponseParameter"]["Authenticator"] = int.from_bytes(datagram[authenticator_index + 1 : authenticator_index + authenticator_length + 1])
        return action_response
    if action_response_type == 9:
        decoder_logger.debug("Decoding a SET_MMI.response...")
        return None

    raise Exception("Datagram does not represent an ACTION.response!")

def decode_attributes_list(datagram, attribute_list_start_index=3):
    datagram_index = attribute_list_start_index

    number_of_attributes_in_list = datagram[datagram_index]
    decoder_logger.debug(f"Number of attributes do decode in the datagram: {number_of_attributes_in_list}")
    datagram_index += 1

    decoded_attribute_list = []
    while len(decoded_attribute_list) < number_of_attributes_in_list:
        attribute_id = datagram[datagram_index]
        decoder_logger.debug(f"Attribute id is {attribute_id} = 0x{attribute_id:02X}")

        # Container Choice or ContainerType
        container_type = datagram[datagram_index + 1]
        decoder_logger.debug(f"Decoding attribute with Container Type {container_type} = 0x{container_type:02X}")
        if container_type in FIXED_SIZE_CONTAINER_TYPE_SIZES:
            length = FIXED_SIZE_CONTAINER_TYPE_SIZES[container_type] + 1
            decoder_logger.debug(f"Attribute has fixed size!")
        elif container_type == ContainerType.VEHICLE_LPN:
            length = datagram[datagram_index + 4] + 4
            decoder_logger.debug(f"Attribute is LPN!")
        else:
            length = datagram[datagram_index + 2]
            decoder_logger.debug(f"Attribute has variable size!")
        decoder_logger.debug(f"Length of attribute including container type is {length} = 0x{length:02X}")

        # Attribute value including its Container Type and optional Length, but without the AttributeId
        attribute_value = datagram[datagram_index + 1 : datagram_index + length + 1]
        datagram_index += length + 1

        attribute_value_bytes = bytes(attribute_value)
        decoder_logger.debug(f"Attribute value in hex: {attribute_value_bytes.hex().upper()}")
        attribute = {
            "attribute_id": attribute_id,
            "value": attribute_value_bytes.hex().upper(),
            "representation": DSRC_Data_Container(attribute_value_bytes).represent_as_dict()
            }
        decoded_attribute_list.append(attribute)
        decoder_logger.debug(f"Appended attribute to list! Current number of decoded attrs: {len(decoded_attribute_list)}")
        attribute_list_size_in_bytes = datagram_index - attribute_list_start_index
    return (decoded_attribute_list, attribute_list_size_in_bytes)

# mandapplications contains AIDs 1, 20 and 29, for EFC, CCC and UNI/IT, respectively
def encode_bst_datagram(frag_header:int, manufacturer_id=0x31, individual_id=0x111, mandapplications=[1, 20, 29], profile=0x00, profile_list=[0x00], non_mand_applications = []):
    """This function encodes/prepares a BST datagram from the provided input parameters"""
    # INITIALIZATION.request is 0b1000, shifted 4 bits
    init_request = 0x80
    
    # 1 bit boolean
    non_mand_applications_present = len(non_mand_applications) != 0
    # Shift it 3 bits to the left to fit the datagram
    non_mand_applications_present = non_mand_applications_present << 3
    
    beacon_id_int = (init_request | non_mand_applications_present) << 40
    
    # manufacturerId has a size of 16 bits
    beacon_id_int |= manufacturer_id << 27
    # individualId has a size of 27 bits
    beacon_id_int |= individual_id
    
    beacon_id = list(beacon_id_int.to_bytes(6))
    
    utc_timestamp = list(int(time.time()).to_bytes(4))
    decoder_logger.debug(f"UTC timestamp in hex format: {bytes(utc_timestamp).hex().upper()}")
    if non_mand_applications_present :
        bst_datagram = [frag_header] + beacon_id + utc_timestamp + [profile] + [len(mandapplications)] + mandapplications + [len(non_mand_applications)] + non_mand_applications + profile_list
    else:
        bst_datagram = [frag_header] + beacon_id + utc_timestamp + [profile] + [len(mandapplications)] + mandapplications + profile_list
    
    
    decoder_logger.debug(f"Encoded BST in hex format: {bytes(bst_datagram).hex().upper()}")

    return bst_datagram
class BST(dict):
    def __init__(self, beacon_id_int, profile, mandapplications, non_mand_applications, profile_list):
        self.beacon_id_int = beacon_id_int
        self.profile = profile
        self.mandapplications = mandapplications
        self.non_mand_applications = non_mand_applications
        self.profile_list = profile_list
    
    def __repr__(self):
        bst_repr = f'''
        Init request + Non_mand_present_bool + Beacon ID: { hex(self.beacon_id_int)[2:].upper() }
        Profile: {self.profile_list}
        Requested AIDs: {self.mandapplications}
        Requested optional AIDs: {self.non_mand_applications}
        Profile List: {self.profile_list}'''
        return bst_repr

    decoder_logger.debug("Detailed BST string representation: {bst_repr}")
class VST(dict):
    def __init__(self, vst_bytes):
        decoder_logger.debug(f"Decoding VST: {vst_bytes.hex().upper()}")
        self["type"] = "VST"

        profile = vst_bytes[2]
        number_of_applications = vst_bytes[3]
        vst_byte_idx = 4

        decoder_logger.debug(f"\nProfile: {profile}")
        self['Profile'] = profile
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
                efc_cm_hex_str = bytes(vst_bytes[vst_byte_idx : vst_byte_idx + 6]).hex().upper()
                decoder_logger.debug(f"\tEFC-CM: {efc_cm_hex_str}")
                current_application_details["EFC-CM"] = efc_cm_hex_str
                vst_byte_idx += 6
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

                rnd_obe = int.from_bytes(vst_bytes[vst_byte_idx : vst_byte_idx+4])
                current_application_details["RndOBE"] = rnd_obe

                decoder_logger.debug(f"\tRndOBE: {rnd_obe:X}")
                vst_byte_idx += 4

            applications.append(current_application_details)
        self['Applications'] = applications

        obe_status_present = vst_bytes[vst_byte_idx] & 0x80
        equipment_class = vst_bytes[vst_byte_idx] & 0x7F
        obe_manufacturer_id = int.from_bytes(vst_bytes[vst_byte_idx+1:vst_byte_idx+3])

        decoder_logger.debug(f"\tEquipment class: {equipment_class}")
        self['EquipmentClass'] = equipment_class
        decoder_logger.debug(f"\tOBE manufacturerId: {obe_manufacturer_id}")
        self['ManufacturerId'] = obe_manufacturer_id
        vst_byte_idx += 1

        if obe_status_present:
            self['ObeStatus'] = vst_bytes[vst_byte_idx]
    
    def get_eid_info(self, eid:int) -> int:
        vst_application_index = -1
        decoder_logger.debug(f"Getting application with EID {eid}")
        for index, application in enumerate(self['Applications']):
            decoder_logger.debug(f"Application details: {application}")
            if application["EID"] == eid:
                vst_application_index = index
        if vst_application_index == -1:
            decoder_logger.info(f"EID {eid} is not present!")
        else:
            decoder_logger.debug(f"Index of EID {eid} on VST is {vst_application_index}")
        return vst_application_index

def decode_vst(vst_bytes):
    return VST(vst_bytes)