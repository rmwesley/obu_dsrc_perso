from bac_l7 import pertel_bac_l7

class TgbvBacL7(pertel_bac_l7.PertelBacL7):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.beacon_id = bytes(6)

    def _tgb_change_beacon_id(self) -> bytes:
        """Command ID 0x53"""
        pass

    def _tgb_read_beacon_id(self) -> bytes:
        """Command ID 0x54"""
        message_content = bytes([0x54])
        return self.send_command(message_content)

    def update_beacon_id(self) -> bytes:
        response_content = self._tgb_read_beacon_id()
        self.beacon_id = bytes(response_content[3:9])
        return self.beacon_id

    def get_beacon_id(self) -> bytes:
        return self.beacon_id

    def _tgb_change_communication_config(self) -> bytes:
        """Command ID 0x55"""
        pass

    def _tgb_read_communication_config(self) -> bytes:
        """Command ID 0x56"""
        pass