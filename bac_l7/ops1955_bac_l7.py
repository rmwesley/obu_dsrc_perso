import json
from bac_l7 import pertel_bac_l7

with open('settings/beacon_manager_config.json', 'r') as beacon_manager_settings_file:
    beacon_manager_settings = json.load(beacon_manager_settings_file)
    chosen_beacon_name = beacon_manager_settings['default_beacon_name']
    bac_l2_config = beacon_manager_settings[chosen_beacon_name]['bac_l2_config']

class Ops1955BacL7(pertel_bac_l7.PertelBacL7):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def _kapsch_set_config(self):
        # STOP the beacon first!!
        await self._pertel_set_beacon_mode(0x03)
        await self._pertel_monitor_beacon()

        await self._kapsch_cd_read_dsrc_config()
        await self._kapsch_cd_set_dsrc_config()
        # We now set its mode to transparent and stop serial communication!
        await self._pertel_set_beacon_mode(0x01)

    async def _kapsch_cd_set_dsrc_config(self) -> bytes:
        """
        Kapsch-specific.
        CD_SET_DSRC_CONFIG
        Message ID 0x61
        """
        msg_id = 0x61 # 97
        msg_data_struct_version = 0x01
        dsrc_channel = 0x01
        bst_repetition_time = 0x00

        bac_l2_config = beacon_manager_settings['OPS1955']['bac_l2_config']
        if bac_l2_config['release_command_config'] == 'UI':
            end_transceiver_behavior = 0x00
        elif bac_l2_config['release_command_config'] == 'ACn':
            end_transceiver_behavior = 0x01

        message_content = bytes([msg_id, msg_data_struct_version, dsrc_channel, bst_repetition_time, end_transceiver_behavior])
        return await self.send_command(message_content=message_content)

    async def _kapsch_cd_read_dsrc_config(self) -> bytes:
        """
        Kapsch-specific.
        CD_READ_DSRC_CONFIG
        Message ID 0x62
        """
        msg_id = 0x62 # 98
        message_content = bytes([msg_id])
        return await self.send_command(message_content=message_content)