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

# def dll_versions():
#     return ops1955_beacon_manager_dll.etc_Versions()
# print(dll_versions())

def etc_write_wrapper(message_id:int, message_content:bytes):
    message_id_16_bits = ctypes.c_int16(message_id)
    ops1955_beacon_manager_dll.etc_Write(ctypes.byref(message_id_16_bits), message_content)

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
    threading.Thread(target=message_queue_polling, daemon=True).start()
    threading.Thread(target=continually_manage_message_queue, daemon=True).start()

    kapsch_dll_loader_logger.info(f"Threads to poll for messages started!!")
    kapsch_dll_loader_logger.debug(f"Sending request to read DSRC config...")
    etc_write_wrapper(message_id=2456, message_content=b'000100000000000000000000000000000000')

    kapsch_dll_loader_logger.debug(f"Sending request to read BST config...")
    etc_write_wrapper(message_id=2458, message_content=b'')

    kapsch_dll_loader_logger.debug(f"Sending request to read TRX status and config...")
    etc_write_wrapper(message_id=1401, message_content=b'010000')

    return result

# The polling function is periodically called in a separate thread
def message_queue_polling():
    global messages_polling_seconds
    # if not messages_polling_seconds:
    #     messages_polling_seconds = 0.5

    while True:
        message_queue_status = ops1955_beacon_manager_dll.etc_Poll()
        # kapsch_dll_loader_logger.debug(f'Current message queue status ({message_queue_status}): {status_description}')
        status_description = message_queue_status_descriptions.get(message_queue_status)
        kapsch_dll_loader_logger.debug(f'Message queue status ({message_queue_status}). Description: {status_description}')
        if message_queue_status == 0:
            message_queue_non_empty_event.clear()
        else:
            message_queue_non_empty_event.set()
        # if message_queue_status > 2:
        #     raise kapsch_dll_loader_logger.error('Error in message!')
        time.sleep(messages_polling_seconds)


def shutdown():
    kapsch_dll_loader_logger.debug(f"Shutting down OPS1955 beacon...")
    result = ops1955_beacon_manager_dll.etc_DeInit()
    kapsch_dll_loader_logger.debug(f"Shut down successfully!!")

def bst_cyclic_emission_wrapper(t_apdu_datagram):
    while not vst_notification_event.wait(0.2):
        send_t_apdu(t_apdu_datagram = t_apdu_datagram)
        # threading.Thread(target=bst_emission).start()
def start_bst_wrapper(t_apdu_datagram, bst_type):
    kapsch_dll_loader_logger.info(f"Emitting BST manually!!")
    # kapsch_dll_loader_logger.warning(f"If BST emission is set to automatic, there is no need to manually send a T-APDU!")
    threading.Thread(target=bst_cyclic_emission_wrapper, args=[t_apdu_datagram], daemon=True).start()

message_waiting_time = 1
message_queue_non_empty_event = threading.Event()
def continually_manage_message_queue():
    while True:
        if message_queue_non_empty_event.wait(message_waiting_time):
            consume_message_from_beacon()
            time.sleep(message_waiting_time)

already_read_message_list = []
MAX_MESSAGE_SIZE = 255
def read_message_from_beacon() -> tuple[int, bytes]:
    message_id = ctypes.c_int16(0)
    message_content = ctypes.create_string_buffer(MAX_MESSAGE_SIZE)

    result = ops1955_beacon_manager_dll.etc_Read(ctypes.byref(message_id), message_content)
    message_id_val = message_id.value
    kapsch_dll_loader_logger.debug(f"Message ID: {message_id_val}")
    kapsch_dll_loader_logger.debug(f"Message content: {message_content[0:MAX_MESSAGE_SIZE].hex().upper()}")

    message_tuple = (message_id_val, message_content.value)
    already_read_message_list.append(message_tuple)

    Ops1955_Message_Types = OPS1955.KapschOps1955Message.Message_Types

    choice_tag_dict_key = (2, message_id_val)
    choice_identifier = Ops1955_Message_Types._cont_tags[choice_tag_dict_key]

    kapsch_dll_loader_logger.debug(f'Message ID corresponding CHOICE identifier: {choice_identifier}')

    message_content_type = Ops1955_Message_Types._cont[choice_identifier]
    kapsch_dll_loader_logger.debug(f'Message content type: {message_content_type}')
    message_content_type.from_aper(message_content[0:MAX_MESSgitAGE_SIZE])

    Ops1955_Message_Types.set_val((choice_identifier, message_content_type._val))
    kapsch_dll_loader_logger.debug(f'Message in ASN:\n{Ops1955_Message_Types.to_asn1()}')

    # choice_index = Ops1955_Message_Types._root.index(choice_identifier)    
    # kapsch_dll_loader_logger.debug(f'Message ID corresponding CHOICE index: {choice_index}')
    # message_uper_val = choice_index.to_bytes(length=2, byteorder='little') + message_content[0:MAX_MESSAGE_SIZE]

    # kapsch_dll_loader_logger.debug(f'Message in UPER: {message_uper_val.hex().upper()}')
    # Ops1955_Message_Types.from_uper(message_uper_val)

    # kapsch_dll_loader_logger.debug(f'Message in ASN: {Ops1955_Message_Types.to_asn1()}')

    return message_tuple
    # response_t_apdu = bytes(message_id, message_content[0:MAX_MESSAGE_SIZE])

def get_latest_message_list():
    return already_read_message_list

def consume_message_from_beacon():
    notify_vst_message_id = 12

    message_id, message_content = read_message_from_beacon()
    kapsch_dll_loader_logger.info(f'Message ({message_id}) received!')

    message_description = message_id_descriptions.get(message_id)
    kapsch_dll_loader_logger.debug(f'Message ID is {message_id}. Description: {message_description}')
    kapsch_dll_loader_logger.debug(f'Message content in hex: {message_content.hex().upper()}')

    if message_id == notify_vst_message_id:
        vst_notification_event.set()


def handle_already_read_messages():
    notify_vst_message_id = 12

    read_message_from_beacon()
    for message_id, message_content in already_read_message_list:
        if message_id == notify_vst_message_id:
            vst_notification_event.set()

    return True


vst_notification_event = threading.Event()
latest_vst = None
def wait_for_vst_event():
    while not vst_notification_event.wait(5):
        kapsch_dll_loader_logger.info("Waiting for VST notification...")
    kapsch_dll_loader_logger.info("No longer waiting for VST!")
    pass


def get_vst():
    return latest_vst

def send_t_apdu(t_apdu_datagram: bytes):
    kapsch_dll_loader_logger.debug(f"[TGBV L7]: Sending T-APDU! T-APDU value in hex: {t_apdu_datagram.hex().upper()}")

    t_apdu_type = t_apdu_datagram[0]
    # t_apdu_content = t_apdu_datagram << 4
    # t_apdu_content = (int.from_bytes(t_apdu_datagram, byteorder='big') << 4).to_bytes(byteorder='big')
    t_apdu_content = bitarray.bitarray()
    t_apdu_content.frombytes(t_apdu_datagram)
    t_apdu_content = t_apdu_content << 4
    t_apdu_content = t_apdu_content.tobytes()

    kapsch_dll_loader_logger.debug(f"[TGBV L7]: T-APDU content in hex: {t_apdu_content.hex().upper()}")

    etc_write_wrapper(message_id=t_apdu_type, message_content=t_apdu_content)
    kapsch_dll_loader_logger.debug(f"[TGBV L7]: Successfully sent T-APDU!")

def receive_t_apdu():
    kapsch_dll_loader_logger.debug(f"[TGBV L7]: Receiving T-APDU!")

    received_t_apdu = ops1955_beacon_manager_dll.etc_Read()
    kapsch_dll_loader_logger.debug(f"T-APDU value in hex: {received_t_apdu.hex().upper()}")
    return received_t_apdu

def send_command(t_apdu_datagram: bytes):
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

# print(l7_trx_drv_get_chipID())
# ops1955_l7_dll.l7_trx_drv_interface_start()
# ops1955_l7_dll.l7_trx_drv_interface_start_with_full_status()
# ops1955_l7_dll.l7_trx_drv_interface_stop()