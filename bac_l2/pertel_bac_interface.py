import logging
import serial
import json
import time
from bac_l2 import bac_l2_host2beacon

bac_serial_wrapper_logger = logging.getLogger(__name__)
    
MAXIMUM_DSRC_L7_COMMAND_SIZE = 118
class PertelBacL2(bac_l2_host2beacon.BacHost):
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