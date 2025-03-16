from bac_l2 import pertel_bac_interface

class Ops1955BacL2(pertel_bac_interface.PertelBacL2):
    def _kapsch_set_config(self):
        self.initialize_bac_serial_communication()

        # STOP the beacon first!!
        _pertel_set_beacon_mode(0x03)
        _pertel_monitor_beacon()

        _kapsch_cd_read_dsrc_config()
        _kapsch_cd_set_dsrc_config()
        # We now set its mode to transparent and stop serial communication!
        _pertel_set_beacon_mode(0x01)
        close()

    def _kapsch_cd_set_dsrc_config(self) -> bytes:
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
        return self.send_command(message_content=message_content)

    def _kapsch_cd_read_dsrc_config() -> bytes:
        """
        Kapsch-specific.
        CD_READ_DSRC_CONFIG
        Message ID 0x62
        """
        msg_id = 0x62 # 98
        message_content = bytes([msg_id])
        return self.send_command(message_content=message_content)