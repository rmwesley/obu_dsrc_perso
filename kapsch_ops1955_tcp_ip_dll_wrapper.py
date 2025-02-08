import ctypes
# from ctypes import POINTER, wintypes, c_char_p, c_uint, c_int, c_byte, c_bool, c_ulong, c_ushort, c_void_p
# from ctypes.wintypes import HWND, LPCWSTR, UINT, BYTE, WORD, DWORD, CHAR, BOOL, LPVOID, LPBYTE

import time
import threading
import logging

import bitarray
from ASN.compiled_DSRC_instances import OPS1955

message_queue_status_descriptions = {
    0: "OK, no message to read",
    1: """WARNING there are more messages to read before poll.
    This warning will be asserted only once.""",
    2: "Message to read",
    7: "Unknown return code from hpc_Poll",
    8: "driver not initialized",
    9: "driver lost connection to device",
}

message_id_descriptions = {
    0: "T-APDU of type ACTION.request, from ISO 14906",
    1: "T-APDU of type ACTION.response, from ISO 14906",
    2: "T-APDU of type EVENT_REPORT.request, from ISO 14906",
    3: "T-APDU of type EVENT_REPORT.response, from ISO 14906",
    4: "T-APDU of type SET.request, from ISO 14906",
    5: "T-APDU of type SET.response, from ISO 14906",
    6: "T-APDU of type GET.request, from ISO 14906",
    7: "T-APDU of type GET.response, from ISO 14906",
    8: "T-APDU of type INITIALISATION.request, from ISO 14906",
    9: "T-APDU of type INITIALISATION.response, from ISO 14906",
    12: "Notify_Application_Beacon (NAB), for VSTs!",
    1401: "Read TRX status",
    1423: "OPS1955 Infrared sensor detected changes!!",
    2451: "Read DSRC link mode",
    2456: "Read DSRC configuration",
    2458: "Read BST configuration"
}

kapsch_dll_loader_logger = logging.getLogger(__name__ + ".loader")

# Porting the Kapsch OPS1955 LiC Driver DLL to Python. It exports 8 functions

# Remember to add the "beacon_drivers/OPS1955/" dir to the PATH environment variable!!
kapsch_dll_loader_logger.debug("Loading licetc_gen.dll...")
ops1955_beacon_manager_dll = ctypes.cdll.LoadLibrary(f"beacon_drivers/OPS1955/licetc_gen.dll")

last_error_code = ctypes.windll.kernel32.GetLastError()
if last_error_code:
    raise kapsch_dll_loader_logger.error(f"Error loading DLL! Error code: {last_error_code}")

print(f"DLL base address in hex: 0x{ops1955_beacon_manager_dll._handle:0X}")
print(ops1955_beacon_manager_dll.__dict__)

# DLL function wrappers
def dll_version() -> int:
    return ops1955_beacon_manager_dll.etc_Version()
print(f"DLL version: {dll_version()}")

def etc_write_message_choice_identifier_content_wrapper(choice_identifier:str, msg_cont_val:dict):
    message_id, message_oer_val = encode_kapsch_request_value_to_id_and_oer(choice_identifier, msg_cont_val)
    
    etc_write_message_id_content_wrapper(message_id, message_oer_val)

def etc_write_message_id_content_wrapper(message_id:int, msg_cont_oer_val:bytes):
    message_id_16_bits = ctypes.c_int16(message_id)
    return_val = ops1955_beacon_manager_dll.etc_Write(ctypes.byref(message_id_16_bits), msg_cont_oer_val)
    kapsch_dll_loader_logger.debug(f"[OPS1955] >>> Wrote message with ID ({message_id}), return was ({return_val})")

def sent_set_bst_config_requests(t_apdu_datagram:bytes):
    OPS1955.EfcDsrcGeneric.T_APDUs.from_uper(t_apdu_datagram)
    t_apdu_val = OPS1955.EfcDsrcGeneric.T_APDUs._val

    kapsch_dll_loader_logger.info(f"Setting BST config...")

    t_apdu_tag, bst_value = t_apdu_val
    assert t_apdu_tag == 'initialisation-request'

    # Removing unnecessary fields for Kapsch BST Config
    bst_config_value = bst_value
    del bst_config_value['time']
    del bst_config_value['profileList']

    kapsch_dll_loader_logger.info(f'[OP1955] > Sending set-bst-configuration with config value:\n{bst_config_value}')
    # Changing Message ID from initialisation-request [8] to set-bst-configuration [2457]
    etc_write_message_choice_identifier_content_wrapper(choice_identifier='set-bst-configuration', msg_cont_val=bst_config_value)
    
    kapsch_dll_loader_logger.info(f"[OP1955] > Wrote message to set BST!")
    
    kapsch_dll_loader_logger.info(f"[OP1955] > Writing message to read BST config...")
    etc_write_message_id_content_wrapper(message_id=2458, msg_cont_oer_val=b'')

def send_config_read_requests():
    message_writing_timeout = 0.5
    kapsch_dll_loader_logger.debug(f"Waiting {timeout_s}s between config requests")
    time.sleep(timeout_s)

    kapsch_dll_loader_logger.debug(f"[OPS1955] >> Sending Read DSRC config request...")
    etc_write_message_id_content_wrapper(message_id=2456, msg_cont_oer_val=b'')
    time.sleep(timeout_s)
    
    kapsch_dll_loader_logger.debug(f"[OPS1955] >> Sending Read DSRC link mode request...")
    etc_write_message_id_content_wrapper(message_id=2451, msg_cont_oer_val=b'')
    time.sleep(timeout_s)

    kapsch_dll_loader_logger.debug(f"[OPS1955] >> Sending Read Time request...")
    etc_write_message_id_content_wrapper(message_id=2460, msg_cont_oer_val=b'')
    time.sleep(timeout_s)

    kapsch_dll_loader_logger.debug(f"[OPS1955] >> Sending Read TRX status and config request...")
    etc_write_message_id_content_wrapper(message_id=1401, msg_cont_oer_val=b'')
    time.sleep(timeout_s)

messages_polling_seconds = 1
def ops1955_init(
    ip_address: bytes = bytes([127, 0, 0, 1]),
    tx_tcp_port: int = 4993,
    rx_tcp_port: int = 4994,
    trx_tcp_port: int = 4997,
    lic_tcp_port: int = 4998,
    blocking_read: bool = False
) -> int:
    kapsch_dll_loader_logger.debug(f"Initializing OPS1955 beacon...")
    result = ops1955_beacon_manager_dll.etc_Init(ip_address, tx_tcp_port, rx_tcp_port, trx_tcp_port, lic_tcp_port, blocking_read)
    kapsch_dll_loader_logger.info(f"Successfully initialized OPS1955 beacon!!")

    kapsch_dll_loader_logger.debug(f"We immediately start polling for new messages...")
    # These message managers run in separate threads
    message_queue_status_polling_thread = threading.Thread(target=message_queue_status_polling, daemon=True).start()
    message_reader_thread = threading.Thread(target=kapsch_msg_reader, daemon=True).start()

    kapsch_dll_loader_logger.info(f"Threads to poll for messages started!!")

    return result

# The polling function is periodically called in a separate thread
def message_queue_status_polling():
    global messages_polling_seconds

    while True:
        message_queue_status = ops1955_beacon_manager_dll.etc_Poll()
        status_description = message_queue_status_descriptions.get(message_queue_status)
        kapsch_dll_loader_logger.debug(f'Message queue status ({message_queue_status}). Description: {status_description}')
        if message_queue_status == 0:
            message_queue_non_empty_event.clear()
        else:
            message_queue_non_empty_event.set()
        time.sleep(messages_polling_seconds)

def shutdown():
    kapsch_dll_loader_logger.debug(f"Shutting down OPS1955 beacon...")
    result = ops1955_beacon_manager_dll.etc_DeInit()
    kapsch_dll_loader_logger.debug(f"Shut down successfully!!")

def bst_cyclic_emission_wrapper():
    while not vst_notification_event.wait(0.2):
        etc_write_message_id_content_wrapper(17, b'')
    kapsch_dll_loader_logger.info(f"Successfully emitted a BST!!")

def sent_set_dsrc_trx_config_requests():
    kapsch_dll_loader_logger.info(f"[OPS1955] > Sending set-dsrc-link-mode (2450) with Single Shot (3)...")
    etc_write_message_choice_identifier_content_wrapper(choice_identifier='set-dsrc-link-mode', msg_cont_val={'mode': 3})
    kapsch_dll_loader_logger.info(f"[OPS1955] > Sending set-trx-my-power-mode (1405) with mode (2, ON)")
    etc_write_message_choice_identifier_content_wrapper(choice_identifier='set-trx-my-power-mode', msg_cont_val={'instance': 1, 'mode': 2})

    time.sleep(1)
    
    # kapsch_dll_loader_logger.info(f"[OPS1955] > Sending read-dsrc-link-mode (2451)")
    # etc_write_message_choice_identifier_content_wrapper(choice_identifier='read-dsrc-link-mode', msg_cont_val=0)
    # kapsch_dll_loader_logger.info(f"[OPS1955] > Sending read-trx-status (1401)")
    # etc_write_message_choice_identifier_content_wrapper(choice_identifier='read-trx-status', msg_cont_val={'instance': 1})
    # kapsch_dll_loader_logger.info(f"[OPS1955] > Sending read-ui-status (1422)")
    # etc_write_message_choice_identifier_content_wrapper(choice_identifier='read-ui-status', msg_cont_val=0)

def start_bst_wrapper(t_apdu_datagram:bytes, bst_type:int):
    kapsch_dll_loader_logger.debug(f"[OPS1955] > We send set a BST config request...")
    sent_set_bst_config_requests(t_apdu_datagram)
    
    kapsch_dll_loader_logger.debug(f"[OPS1955] > We send DSRC & TRX set config requests...")
    sent_set_dsrc_trx_config_requests()

    automatic_bst = True
    if not automatic_bst:
        manually_send_bst()
    
def manually_send_bst():
    kapsch_dll_loader_logger.info(f"Emitting BST manually...")
    threading.Thread(target=bst_cyclic_emission_wrapper, daemon=True).start()

message_waiting_time = 1
message_queue_non_empty_event = threading.Event()
def kapsch_msg_reader():
    while True:
        if message_queue_non_empty_event.wait(message_waiting_time):
            read_message_from_queue()
            time.sleep(message_waiting_time)
        else:
            kapsch_dll_loader_logger.info(f"Message queue empty!")

def encode_kapsch_request_value_to_id_and_oer(choice_identifier: str, msg_cont_val: dict) -> tuple[int, bytes]:
    # Message ID (int)
    content_type = OPS1955.KapschOps1955Message.KapschRequestMessages._cont[choice_identifier]
    message_id = content_type._tag[0]

    # oer content (bytes)
    content_type.set_val(msg_cont_val)
    message_oer_val = content_type.to_oer()

    kapsch_dll_loader_logger.info(f'[OPS1955] >>> Request Message {message_id} OER value in hex: {message_oer_val.hex().upper()}')
    
    kapsch_message_val = (choice_identifier, msg_cont_val)
    OPS1955.KapschOps1955Message.KapschRequestMessages.set_val(kapsch_message_val)
    kapsch_dll_loader_logger.info(f"[OPS1955] >>> Encoded message ({message_id}) to send:\n{OPS1955.KapschOps1955Message.KapschRequestMessages.to_asn1()}")
    return message_id, message_oer_val

def decode_kapsch_request_msg_cont_from_msg_id_and_oer_val(message_id:int, msg_oer_val:bytes) -> tuple[str, dict]:
    Ops1955_Request = OPS1955.KapschOps1955Message.KapschRequestMessages
    choice_tag_dict_key = (2, message_id)
    choice_identifier = Ops1955_Request._cont_tags[choice_tag_dict_key]

    kapsch_dll_loader_logger.debug(f'[OPS1955] > Request CHOICE identifier: {choice_identifier} (Tag {message_id})')

    message_content_type = Ops1955_Request._cont[choice_identifier]
    # kapsch_dll_loader_logger.debug(f'Read Message content type: {message_content_type.__dict__}')
    message_content_type.from_oer(msg_oer_val)
    # kapsch_dll_loader_logger.debug(f'[OPS1955] > Request content value:\n{message_content_type._val}')

    Ops1955_Request.set_val((choice_identifier, message_content_type._val))
    kapsch_dll_loader_logger.info(f'[OPS1955] > Request in ASN:\n{Ops1955_Request.to_asn1()}')

    # kapsch_dll_loader_logger.debug(f'Message in oer in hex: {Ops1955_Request.to_oer().hex().upper()}')

    # kapsch_dll_loader_logger.debug(f'_root:\n{Ops1955_Request._root}')
    # choice_index = Ops1955_Request._root.index(choice_identifier)
    # kapsch_dll_loader_logger.debug(f'Choice index:\n{choice_index}')
    kapsch_message = Ops1955_Request._val
    return kapsch_message

def encode_kapsch_response_value_to_id_and_oer(choice_identifier: str, msg_cont_val: dict) -> tuple[int, bytes]:
    # Message ID (int)
    content_type = OPS1955.KapschOps1955Message.KapschResponseMessages._cont[choice_identifier]
    message_id = content_type._tag[0]

    # oer content (bytes)
    content_type.set_val(msg_cont_val)
    message_oer_val = content_type.to_oer()

    kapsch_dll_loader_logger.debug(f'[OPS1955] <<< Response ({message_id}) OER value in hex: {message_oer_val.hex().upper()}')
    kapsch_dll_loader_logger.debug(f'[OPS1955] <<< Response ({message_id}) in ASN: {content_type.to_asn1()}')

    return message_id, message_oer_val

def decode_kapsch_response_msg_cont_from_msg_id_and_oer_val(message_id:int, msg_oer_val:bytes) -> tuple[str, dict]:
    Ops1955_Response = OPS1955.KapschOps1955Message.KapschResponseMessages
    choice_tag_dict_key = (2, message_id)
    choice_identifier = Ops1955_Response._cont_tags[choice_tag_dict_key]

    kapsch_dll_loader_logger.debug(f'[OPS1955] <<< Response CHOICE identifier: {choice_identifier} (Tag {message_id})')

    message_content_type = Ops1955_Response._cont[choice_identifier]
    message_content_type.from_oer(msg_oer_val)

    Ops1955_Response.set_val((choice_identifier, message_content_type._val))
    kapsch_dll_loader_logger.info(f"[OPS1955] <<< Response ({message_id}) OER value in hex: {message_content_type.to_oer().hex().upper()}")
    kapsch_dll_loader_logger.info(f'[OPS1955] <<< Response ({message_id}) in ASN:\n{Ops1955_Response.to_asn1()}')

    kapsch_message = Ops1955_Response._val
    return kapsch_message

already_read_message_list = []
MAX_MESSAGE_SIZE = 255

def etc_read_wrapper() -> tuple[int, bytes]:
    message_id = ctypes.c_int16(0)
    message_content = ctypes.create_string_buffer(MAX_MESSAGE_SIZE)

    result = ops1955_beacon_manager_dll.etc_Read(ctypes.byref(message_id), message_content)
    kapsch_dll_loader_logger.debug(f"[OPS1955] <<<<< Successfully read a message! ({result})")

    message_id_val = message_id.value

    message_description = message_id_descriptions.get(message_id_val)
    kapsch_dll_loader_logger.debug(f'[OPS1955] <<<<< Message ID is {message_id_val}. Description: {message_description}')
    kapsch_message_cont_oer_val = message_content[0:MAX_MESSAGE_SIZE]
    kapsch_dll_loader_logger.debug(f"[OPS1955] <<<<< Raw Response Message ({message_id_val}) in hex: {kapsch_message_cont_oer_val.hex().upper()}")

    message_tuple = (message_id_val, kapsch_message_cont_oer_val)
    already_read_message_list.append(message_tuple)

    return message_tuple

def get_latest_message_list():
    return already_read_message_list

vst_notification_event = threading.Event()
def read_message_from_queue():
    Notify_Application_Beacon_MID = 12

    message_id, message_cont_oer_val = etc_read_wrapper()

    decode_kapsch_response_msg_cont_from_msg_id_and_oer_val(message_id, message_cont_oer_val)
    if message_id == Notify_Application_Beacon_MID:
        vst_notification_event.set()

def handle_already_read_messages():
    Notify_Application_Beacon_MID = 12

    etc_read_wrapper()
    for message_id, message_content in already_read_message_list:
        if message_id == Notify_Application_Beacon_MID:
            vst_notification_event.set()

    return True


latest_vst = None
def wait_for_vst_event():
    while not vst_notification_event.wait(3):
        kapsch_dll_loader_logger.info("Waiting for VST notification...")
    kapsch_dll_loader_logger.error("No longer waiting for VST!")
    pass


def get_vst():
    return latest_vst

def convert_t_apdu_to_kapsch_message(t_apdu_datagram : bytes) -> tuple[int, bytes]:
    kapsch_dll_loader_logger.debug(f"[Converter]: Converting T-APDU to KapschMessage")
    OPS1955.EfcDsrcGeneric.T_APDUs.from_uper(t_apdu_datagram)
    t_apdu_value = OPS1955.EfcDsrcGeneric.T_APDUs._val

    kapsch_dll_loader_logger.debug(f"[Converter]: T-APDU value:\n{t_apdu_value}")
    OPS1955.KapschOps1955Message.KapschRequestMessages.set_val(t_apdu_value)

    # kapsch_dll_loader_logger.debug(f"[Converter]: KapschMessage value:\n{OPS1955.KapschOps1955Message.KapschRequestMessages._val}")
    # kapsch_dll_loader_logger.debug(f"[Converter]: KapschMessage:\n{OPS1955.KapschOps1955Message.KapschRequestMessages.__dict__}")

    choice_identifier = OPS1955.KapschOps1955Message.KapschRequestMessages._val[0]
    message_cont_type = OPS1955.KapschOps1955Message.KapschRequestMessages._cont[choice_identifier]
    # kapsch_dll_loader_logger.debug(f"[Converter]: Message content type:\n{message_content_type.__dict__}")
    message_id = message_cont_type._tag[0]
    kapsch_dll_loader_logger.debug(f"[Converter]: Message ID: {message_id}")

    message_content_value = OPS1955.KapschOps1955Message.KapschRequestMessages._val[1]
    message_cont_type.set_val(message_content_value)
    kapsch_dll_loader_logger.debug(f"[Converter]: Message content value: {message_cont_type._val}")
    message_cont_oer_val = message_cont_type.to_oer()
    kapsch_dll_loader_logger.debug(f"[Converter]: Message content in hex: {message_cont_oer_val.hex().upper()}")

    kapsch_dll_loader_logger.debug(f"Converted T-APDU to KapschMessage with ID {message_id} and content {message_cont_type._val}")
    return message_id, message_cont_oer_val

def send_t_apdu(t_apdu_datagram: bytes) -> tuple[int, bytes]:
    kapsch_dll_loader_logger.debug(f"[OPS1955 L7]: Sending T-APDU! T-APDU value in hex: {t_apdu_datagram.hex().upper()}")
    message_id, msg_cont_oer_val = convert_t_apdu_to_kapsch_message(t_apdu_datagram)

    etc_write_message_id_content_wrapper(message_id=message_id, msg_cont_oer_val=msg_cont_oer_val)
    return message_id, msg_cont_oer_val

def receive_t_apdu():
    kapsch_dll_loader_logger.debug(f"[OPS1955 L7]: Receiving T-APDU!")

    received_t_apdu = ops1955_beacon_manager_dll.etc_Read()
    kapsch_dll_loader_logger.debug(f"T-APDU value in hex: {received_t_apdu.hex().upper()}")
    return received_t_apdu

def send_req_t_apdu_and_receive_resp_t_apdu(t_apdu_datagram: bytes):
    send_t_apdu(t_apdu_datagram)
    return receive_t_apdu()

def change_trx_mode(operating_mode_code):
    pass

beacon_state = None
def update_state():
    pass

last_beacon_id = bytes()
def update_beacon_id():
    pass

mode = 3 #Transparent
def is_mode(mode_code: str):
    return mode == mode_code

def check_if_transaction_in_progress():
    return False