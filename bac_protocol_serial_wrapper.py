import logging
import serial
import json
import time

bac_serial_wrapper_logger = logging.getLogger(__name__)

def crc16_arc(data : bytearray):
    crc = 0
    for byte_val in data:
        crc ^= byte_val
        for j in range(8):
            if ((crc & 0x1) == 1):
                crc = int((crc / 2)) ^ 40961
            else:
                crc = int(crc / 2)
    return crc & 0xFFFF

with open('settings/beacon_manager_config.json', 'r') as beacon_manager_settings_file:
    beacon_manager_settings = json.load(beacon_manager_settings_file)

MAXIMUM_BAC_COMMAND_RESPONSE_SIZE = 119
def initialize_serial_communication() -> serial.Serial:
    global serial_instance

    bac_serial_wrapper_logger.info(f"Initializing BAC protocol serial communication with beacon...!!")

    chosen_beacon_name = beacon_manager_settings['default_beacon_name']
    serial_config = beacon_manager_settings[chosen_beacon_name]['serial_config']
    port_number = serial_config['beacon_serial_port']

    serial_instance = serial.serial_for_url(
        url = f'COM{port_number}' ,
        baudrate = serial_config['baud_rate'],
        parity = serial_config['parity'],
        stopbits = serial_config['stop_bits'],
        timeout=0.2
    )
    bac_serial_wrapper_logger.info(f"Successfully initialized BAC protocol serial wrapper!")

    return serial_instance

def close():
    global serial_instance
    return serial_instance.close()

RESPONSE_SIZES = {
    0x00: 4,
    0x01: 4
}

ENQ = bytes([0x05]) # Request the transmission of a message
ACK = bytes([0x06]) # Positive acknowledgement (message can be sent!!)
NAK = bytes([0x15]) # Negative acknowledgement (message CANNOT be sent!)
EOT = bytes([0x04]) # End Of Transmission of message
DLE = bytes([0x10]) # Escape character, to discriminate between special characters and message content
STX = bytes([0x02]) # Start of message
ETX = bytes([0x03]) # End of message

def wait_for_beacon_ack() -> bool:
    bac_serial_wrapper_logger.debug('Waiting for an ACK to the last sent message...')
    response_control_str = b''
    while response_control_str != ACK:
        time.sleep(0.1)
        response_control_str = serial_instance.read(1)
    return True

def check_and_wait_until_available_to_write() -> bool:
    bac_serial_wrapper_logger.debug('Sending ENQ and waiting for beacon ACK (asking to transmit message)...')
    response_control_str = b''
    # no_ack_count = 0
    while response_control_str != ACK:
        serial_instance.write(ENQ)
        time.sleep(0.001)
        response_control_str = serial_instance.read(1)
        if response_control_str == b'':
            time.sleep(0.1)
            continue
        response_control_char = response_control_str[0]
        if response_control_str == NAK:
            bac_serial_wrapper_logger.error(f"ENQ (0x05) control char response: 0x{response_control_char:02x}")
        else:
            bac_serial_wrapper_logger.debug(f"ENQ (0x05) control char response: 0x{response_control_char:02x}")
    return True

def check_and_wait_until_available_to_read() -> bool:
    bac_serial_wrapper_logger.debug('Waiting for ENQ from beacon, so we can send an ACK (beacon asking to transmit message)...')
    beacon_req_control_str = b''
    while beacon_req_control_str != ENQ:
        time.sleep(0.2)
        beacon_req_control_str = serial_instance.read(1)
        if beacon_req_control_str != b'':
            beacon_req_control_char = beacon_req_control_str[0]
            bac_serial_wrapper_logger.debug(f"Beacon request control char: 0x{beacon_req_control_char:02x}")
    # Got an ENQ from beacon!
    serial_instance.write(ACK)
    return True

def wrap_message(message_content:bytes) -> bytes:
    """Wrap message contents with control characters and append its CRC16 (Checksum) at the end"""
    message_frame = DLE + STX + message_content + DLE + ETX
    # We skip the first 2 bytes (DLE and STX) to compute the CRC-16 of the message!!
    crc16_int = crc16_arc(message_frame[2:])
    crc16_bytes = int.to_bytes(crc16_int, length=2, byteorder='little')
    return message_frame + crc16_bytes

def send_command(message_content:bytes):
    global serial_instance
    bac_serial_wrapper_logger.debug(f"[BAC >>] Sending message with content 0x{message_content.hex().upper()}")

    check_and_wait_until_available_to_write()

    message_value = wrap_message(message_content)
    serial_instance.write(message_value)
    bac_serial_wrapper_logger.debug(f"[BAC >>] Wrote message 0x{message_value.hex().upper()}")
    wait_for_beacon_ack()

    serial_instance.write(EOT)
    bac_serial_wrapper_logger.debug(f"[BAC >>] Wrote EOT, 0x05, to signal end of transmission")

    check_and_wait_until_available_to_read()
    read_message()

def read_message() -> bytes:
    bac_serial_wrapper_logger.debug('Reading serial response from beacon')
    beacon_msg_content = bytearray()
    current_char = serial_instance.read(1)
    print(current_char)
    while current_char != DLE:
        current_char = serial_instance.read(1)
        beacon_msg_content.append(current_char[0])
        if current_char == STX:
            break
        time.sleep(0.1)

    bac_serial_wrapper_logger.debug('Reading over!! Sending ACK!')
    serial_instance.write(ACK)
    
    bac_serial_wrapper_logger.debug(f"[BAC <<] Read 0x{beacon_msg_content.hex().upper()}")
    return beacon_msg_content

# def send_command_and_receive_response(message_content:bytes) -> bytes:
#     global serial_instance

#     send_command(message_content)

#     response_content = read_message()

#     response_code = response_content[0]
#     if command_code != response_code:
#         raise Exception('[BAC <<] Response code does not match command/request code!!')
#     error_code = response_content[1]
#     if error_code == 0:
#         response_body = serial_instance.read(response_size - 2)
#     else:
#         raise Exception(f'[BAC <<] Error {error_code}')
#     return response

def pertel_set_beacon_mode(mode_code=0) -> bytes:
    """
    The PERTEL modes are:
    0x00: STOP
    0x01: TRANSPARENT
    0x03: MAINTENANCE
    """
    message_content = bytes([0, mode_code])
    return send_command(message_content)

def pertel_monitor_beacon() -> bytes:
    message_content = bytes([0x01])
    return send_command(message_content)

def _kapsch_set_config():
    initialize_serial_communication()

    # STOP the beacon first!!
    pertel_set_beacon_mode(0x03)
    pertel_monitor_beacon()

    _kapsch_cd_read_dsrc_config()
    _kapsch_cd_set_dsrc_config()
    # We now set its mode to transparent and stop serial communication!
    pertel_set_beacon_mode(0x01)
    close()

def _kapsch_cd_set_dsrc_config() -> bytes:
    """
    Kapsch-specific.
    CD_SET_DSRC_CONFIG
    Message ID 0x61
    """

    msg_id = 0x61 # 97
    msg_data_struct_version = 0x01
    dsrc_channel = 0x01
    bst_repetition_time = 0x00

    l2_config = beacon_manager_settings['OPS1955']['serial_config']['l2_config']
    if l2_config['release_command_config'] == 'UI':
        end_transceiver_behavior = 0x00
    elif l2_config['release_command_config'] == 'ACn':
        end_transceiver_behavior = 0x01

    message_content = bytes([msg_id, msg_data_struct_version, dsrc_channel, bst_repetition_time, end_transceiver_behavior])
    return send_command(message_content=message_content)

def _kapsch_cd_read_dsrc_config() -> bytes:
    """
    Kapsch-specific.
    CD_READ_DSRC_CONFIG
    Message ID 0x62
    """
    global serial_instance
    msg_id = 0x62 # 98
    message_content = bytes([msg_id])
    return send_command(message_content=message_content)