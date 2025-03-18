from bac_l7 import pertel_bac_interface

class TgbvBacL2(pertel_bac_interface.PertelBacL2):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _tgb_change_beacon_id(self) -> bytes:
        """Command ID 0x53"""
        pass

    def _tgb_read_beacon_id(self) -> bytes:
        """Command ID 0x54"""
        message_content = bytes([0x54])
        return self.send_command(message_content)

    def get_beacon_id(self) -> bytes:
        response_content = self._tgb_read_beacon_id()
        beacon_id = bytes(response_content[3:9])
        return beacon_id

    def _tgb_change_communication_config(self) -> bytes:
        """Command ID 0x55"""
        pass

    def _tgb_read_communication_config(self) -> bytes:
        """Command ID 0x56"""
        pass