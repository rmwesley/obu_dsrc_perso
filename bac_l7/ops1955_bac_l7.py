import json
from bac_l7 import pertel_bac_l7

with open('settings/beacon_manager_config.json', 'r') as beacon_manager_settings_file:
    beacon_manager_settings = json.load(beacon_manager_settings_file)
    chosen_beacon_name = beacon_manager_settings['default_beacon_name']
    bac_l2_config = beacon_manager_settings[chosen_beacon_name]['bac_l2_config']

class Ops1955BacL7(pertel_bac_l7.PertelBacL7):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def kapsch_set_config_from_settings(self):
        # STOP the beacon first!!
        await self._pertel_set_beacon_mode(0x00)
        await self._pertel_monitor_beacon()

        await self._kapsch_cd_read_dsrc_config()
        await self._kapsch_cd_set_dsrc_config_from_settings()
        # We now set its mode to transparent and stop serial communication!
        await self._pertel_set_beacon_mode(0x01)

    async def _kapsch_cd_set_dsrc_config(self,
        msg_data_struct_version: int,
        dsrc_channel: int,
        bst_repetition_time_ms: int,
        beacon_id_behavior: int,
        end_transceiver_behavior:int
        ) -> bytes:
        """
        Kapsch-specific.
        CD_SET_DSRC_CONFIG
        Message ID 0x61

        msg_data_struct_version (int)
            0x01: Version of the data structure

        dsrc_channel (int)
            0x01: 5,7975 GHz
            0x02: 5,8025 GHz
            0x03: 5,8075 GHz unused
            0x04: 5,8125 GHz unused

        bst_repetition_time_ms (int)
            3 – 255
            Is the minimum time in ms between
            sequentially transmitted BSTs.
        
        beacon_id_behavior (int)
            0x00: The individual part of the
            beacon ID is managed by the device
            and incremented after no reply.
            0x01: The individual part of the
            beacon ID is managed by the host.
            0x02: The beacon ID is managed by
            the device and is incremented after
            each transaction.

        """
        msg_id = 0x61 # 97

        message_content = bytes([msg_id, msg_data_struct_version, dsrc_channel, bst_repetition_time_ms, beacon_id_behavior, end_transceiver_behavior])
        response = await self.send_command(message_content=message_content)

        error_code_int = response[1]
        if error_code_int == 0x03:
            raise Exception("Transceiver not OK")
        if error_code_int == 0x0B:
            raise Exception("Command refused because the parameters are wrong")
        return response

    async def _kapsch_cd_set_dsrc_config_from_settings(self) -> bytes:
        """
        Kapsch-specific.
        CD_SET_DSRC_CONFIG
        Message ID 0x61
        """
        msg_id = 0x61 # 97
        msg_data_struct_version = 0x01
        dsrc_channel = 0x01

        # BST repetition time in ms, between 3ms and 255ms for OPS1955
        bst_repetition_time_ms = 0x03

        # 0x00: Managed by the device and incremented after no reply
        # 0x01: Managed by the host
        # 0x02: Managed by the device and incremented after each transaction
        beacon_id_behavior = 0x02

        bac_l2_config = beacon_manager_settings['OPS1955']['bac_l2_config']
        # ACn mode : Release with Private AC Command, OBE response expected
        # UI mode : Release with 3 Private UI Command emissions, without OBE response 
        if bac_l2_config['release_command_config'] == 'UI':
            end_transceiver_behavior = 0x00
        elif bac_l2_config['release_command_config'] == 'ACn':
            end_transceiver_behavior = 0x01

        response = await self._kapsch_cd_set_dsrc_config(msg_data_struct_version, dsrc_channel, bst_repetition_time_ms, beacon_id_behavior, end_transceiver_behavior)
        return response

    async def _kapsch_cd_read_dsrc_config(self) -> bytes:
        """
        Kapsch-specific.
        CD_READ_DSRC_CONFIG
        Message ID 0x62
        """
        msg_id = 0x62 # 98
        message_content = bytes([msg_id])
        return await self.send_command(message_content=message_content)