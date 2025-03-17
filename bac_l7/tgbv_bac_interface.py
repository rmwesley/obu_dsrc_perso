from bac_l7 import pertel_bac_interface

class TgbvBacL2(pertel_bac_interface.PertelBacL2):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    def _tgb_change_beacon_id(self) -> bytes:
        pass
    def _tgb_read_beacon_id(self) -> bytes:
        pass
    def _tgb_change_communication_config(self) -> bytes:
        pass
    def _tgb_read_communication_config(self) -> bytes:
        pass