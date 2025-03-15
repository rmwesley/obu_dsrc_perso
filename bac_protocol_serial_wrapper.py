import logging
import serial
import json
import time
import bac_l2

bac_serial_wrapper_logger = logging.getLogger(__name__)

with open('settings/beacon_manager_config.json', 'r') as beacon_manager_settings_file:
    beacon_manager_settings = json.load(beacon_manager_settings_file)

MAXIMUM_BAC_COMMAND_RESPONSE_SIZE = 119
def initialize_bac_serial_communication() -> serial.Serial:
    global bac_serial_instance

    bac_serial_wrapper_logger.info(f"Initializing serial communication with beacon...!!")

    chosen_beacon_name = beacon_manager_settings['default_beacon_name']
    serial_config = beacon_manager_settings[chosen_beacon_name]['serial_config']
    port_number = serial_config['beacon_serial_port']

    # This is a byte reading timeout!
    serial_instance = serial.serial_for_url(
        url = f'COM{port_number}' ,
        baudrate = serial_config['baud_rate'],
        parity = serial_config['parity'],
        stopbits = serial_config['stop_bits']
        #timeout=0.2
    )
    bac_serial_wrapper_logger.info(f"Initializing BAC protocol serial communication with beacon...!!")
    bac_serial_instance = bac_l2.BACHost(serial_instance)

    bac_serial_wrapper_logger.info(f"Successfully initialized BAC protocol serial wrapper!")

    return bac_serial_instance

def close():
    global bac_serial_instance
    return bac_serial_instance.close()

RESPONSE_SIZES = {
    0x00: 4,
    0x01: 4
}

def _pertel_set_beacon_mode(mode_code=0) -> bytes:
    global bac_serial_instance
    """
    The PERTEL modes are:
    0x00: STOP
    0x01: TRANSPARENT
    0x03: MAINTENANCE
    """
    message_content = bytes([0, mode_code])
    return bac_serial_instance.send_command(message_content)

def _pertel_monitor_beacon() -> bytes:
    global bac_serial_instance
    message_content = bytes([0x01])
    return bac_serial_instance.send_command(message_content)

def _kapsch_set_config():
    initialize_bac_serial_communication()

    # STOP the beacon first!!
    _pertel_set_beacon_mode(0x03)
    _pertel_monitor_beacon()

    _kapsch_cd_read_dsrc_config()
    _kapsch_cd_set_dsrc_config()
    # We now set its mode to transparent and stop serial communication!
    _pertel_set_beacon_mode(0x01)
    close()

def _kapsch_cd_set_dsrc_config() -> bytes:
    global bac_serial_instance
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
    return bac_serial_instance.send_command(message_content=message_content)

def _kapsch_cd_read_dsrc_config() -> bytes:
    global bac_serial_instance
    """
    Kapsch-specific.
    CD_READ_DSRC_CONFIG
    Message ID 0x62
    """
    global bac_serial_instance
    msg_id = 0x62 # 98
    message_content = bytes([msg_id])
    return bac_serial_instance.send_command(message_content=message_content)