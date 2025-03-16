import logging
import serial
import json
import time
import bac_l2

bac_serial_wrapper_logger = logging.getLogger(__name__)

with open('settings/beacon_manager_config.json', 'r') as beacon_manager_settings_file:
    beacon_manager_settings = json.load(beacon_manager_settings_file)
    chosen_beacon_name = beacon_manager_settings['default_beacon_name']
    
MAXIMUM_DSRC_L7_COMMAND_SIZE = 118
class PertelBacL2(bac_l2.BacHost):
    def initialize_bac_serial_communication(self) -> serial.Serial:
        bac_serial_wrapper_logger.info(f"Initializing serial communication with beacon...!!")

        serial_config = beacon_manager_settings[chosen_beacon_name]['serial_config']
        port_number = serial_config['beacon_serial_port']

        # timeout is for serial byte reading timeout!
        serial_instance = serial.serial_for_url(
            url = f'COM{port_number}' ,
            baudrate = serial_config['baud_rate'],
            parity = serial_config['parity'],
            stopbits = serial_config['stop_bits']
            #timeout=0.2
        )
        bac_serial_wrapper_logger.info(f"Initializing BAC protocol serial communication with beacon...!!")
        self = bac_l2.BacHost(serial_instance)

        bac_serial_wrapper_logger.info(f"Successfully initialized BAC protocol serial wrapper!")

    def set_mode(self, mode_code=0) -> bytes:
        return self._pertel_set_beacon_mode(mode_code)

    def _pertel_set_beacon_mode(self, mode_code=0) -> bytes:
        """
        The PERTEL modes are:
        0x00: STOP
        0x01: TRANSPARENT
        0x03: MAINTENANCE
        """
        message_content = bytes([0, mode_code])
        return self.send_command(message_content)

    def _pertel_monitor_beacon(self) -> bytes:
        message_content = bytes([0x01])
        return self.send_command(message_content)