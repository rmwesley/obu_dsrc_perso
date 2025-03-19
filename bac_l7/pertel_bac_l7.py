import logging
import serial
import json
import time
from bac_l2 import bac_l2_host2beacon
from enum import Enum

bac_serial_wrapper_logger = logging.getLogger(__name__)

class PertelResponseDecodingException(Exception):
    pass
MAXIMUM_DSRC_L7_COMMAND_SIZE = 118

MODE_CHANGE_ERROR_DESCRIPTIONS = {
    0x00: 'No error',
    0x01: 'Command refused due to unknown mode',
    0x02: 'Command refused since a transaction in ongoing',
    0x03: 'Command refused due to problem in the beacon (only when requesting for Transparent mode)',
    0x1D: 'Configuration not applied'
}

class BCM_MODE_Enum(Enum):
    PERTEL_MODE_Stopped = 0x00
    PERTEL_MODE_Transparent = 0x01
    PERTEL_MODE_Maintenance = 0x03

class PertelBacL7(bac_l2_host2beacon.BacHost):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.t_apdu_containing_vst = None
        self.beacon_state = bytes(3)
    def set_mode(self, mode_code=0) -> bytes:
        return self._pertel_set_beacon_mode(mode_code)

    def _decode_pertel_00_response(self, response_content:bytes) -> dict:
        command_id = response_content[0]
        error_code = response_content[1]
        decoded_response = {
            'command_id': command_id,
            'error_message': MODE_CHANGE_ERROR_DESCRIPTIONS[error_code]
        }
        if command_id != 0x00:
            raise PertelResponseDecodingException()
        return

    # def _pertel_set_beacon_mode(self, mode_code=0) -> tuple[bytes, dict]:
    def _pertel_set_beacon_mode(self, mode_code=0) -> bytes:
        """
        Request:
            Command ID, 1 byte:
                0x00
            Functioning mode, 1 byte:
                0x00: STOP
                0x01: TRANSPARENT
                0x03: MAINTENANCE
        Response:
            Command ID, 1 byte:
                0x00
            Error, 1 byte:
                0x00: No error
                0x01: Command refused due to unknown mode
                0x02: Command refused since a transaction in ongoing
                0x03: Command refused due to problem in the beacon (only when requesting for Transparent mode)
                0x1D: Configuration not applied
        """
        message_content = bytes([0, mode_code])
        response_content = self.send_command(message_content)
        # try:
        #     decoded_response = _decode_pertel_00_response(response_content)
        # except:
        #     decoded_response = None
        # return response_content, decoded_response
        return response_content

    def _pertel_monitor_beacon(self) -> bytes:
        """
        Request:
            Command ID, 1 byte:
                0x01
        Response:
            Command ID, 1 byte:
                0x01
            Error, 1 byte:
                0x00: Nothing to report (RAS)
                0x01: Error in command/message length
                0x02: Beacon KO (:O)
                0x0A: Beacon just started
                0x1D: Configuration not applied
            Mode, 1 byte:
                0x00: STOP
                0x01: TRANSPARENT
                0x03: MAINTENANCE
            Transaction in progress, 1 byte:
                0x00: False
                0x01: True
        """
        message_content = bytes([0x01])
        return self.send_command(message_content)
    def update_state(self) -> bytes:
        response_content = self._pertel_monitor_beacon()
        self.beacon_state = bytes(response_content[1:])
        return self.beacon_state
    def get_beacon_state(self) -> bytes:
        return self.beacon_state

    def _pertel_communication_count(self) -> bytes:
        message_content = bytes([0x02])
        return self.send_command(message_content)

    def get_vst(self) -> bytes:
        return self.t_apdu_containing_vst
    def _is_transaction_in_progress(self) -> bool:
        return self.t_apdu_containing_vst != None

    def _pertel_emit_bst_and_get_vst(self, t_apdu_containing_bst:bytes) -> bytes:
        """
        Least significant 3 bits (modulo 8) of BeaconID (individualId) are incremented:
            Every 128 emissions, or
            Every new BST emission request from HOST to Beacon
        Request:
            Command ID, 1 byte:
                0x03
            BST, variable size:
        Response:
            Command ID, 1 byte:
                0x03
            Error, 1 byte:
            VST, variable size:
        """
        message_content = bytes([0x03]) + t_apdu_containing_bst
        response_content = self.send_command(message_content)

        # Removing Command ID 0x03
        self.t_apdu_containing_vst = response_content[1:]
        return response_content

    def pertel_start_bst_emission_and_get_vst(self, t_apdu_containing_bst: bytes, change_beacon_id_periodically:bool = True) -> bytes:
        """Emits BST using helper methods, based on the choice of BeaconID behavior (Normal or Periodically changed)"""
        if not change_beacon_id_periodically:
            return self._pertel_emit_bst_and_get_vst_without_changing_beacon_id(t_apdu_containing_bst)
        return self._pertel_emit_bst_and_get_vst(t_apdu_containing_bst)

    def _pertel_stop_bst_emission(self, t_apdu_bst_datagram:bytes) -> bytes:
        """
        A transaction should not be in progress!
        That is, the beacon did not receive a VST yet!
        Command ID, 1 byte:
            0x04
        Error, 1 byte:
            0x00 : commande acceptée et correctement exécutée
            0x01 : commande refusée car l’antenne de télépéage à
            puissance réduite n'est pas dans le mode transparent ou
            défaut de longueur
            0x02 : commande refusée car une transaction est en cours
            0x1D : configuration non effectuée
        """
        message_content = bytes([0x04])
        return self.send_command(message_content)

    def _pertel_send_dsrc_l7_command_and_close_transaction(self, t_apdu_containing_request:bytes) -> bytes:
        """
        Request:
            Command ID, 1 byte:
                0x05
            Request_T_APDU, variable:
        Response:
            Command ID, 1 byte:
                0x05
            Error, 1 byte:
                00h : commande acceptée et correctement exécutée
                01h : commande refusée car l’antenne de télépéage à
                puissance réduite n'est pas dans le mode transparent ou
                qu'aucune transaction n'est en cours ou défaut de longueur
                03h : commande refusée car problème antenne de
                télépéage à puissance réduite
                09h : commande terminée sur timeout de réponse de l’OBE
                1Dh : configuration non effectuée
            Response_T_APDU, variable:
        """
        message_content = bytes([0x05]) + t_apdu_containing_request
        response_content = self.send_command(message_content)

        # Removing Command ID 0x05
        self.t_apdu_containing_response = response_content[1:]

        # Transaction is over!! Setting VST to None!
        self.t_apdu_containing_vst = None

        return response_content

    def _pertel_send_dsrc_l7_command_and_close_transaction(self, t_apdu_containing_request:bytes) -> bytes:
        """
        Request:
            Command ID, 1 byte:
                0x06
            Request_T_APDU, variable:
        Response:
            Command ID, 1 byte:
                0x06
            Error, 1 byte:
                00h : commande acceptée et correctement exécutée
                01h : commande refusée car l’antenne de télépéage à
                puissance réduite n'est pas dans le mode transparent ou
                qu'aucune transaction n'est en cours ou défaut de longueur
                03h : commande refusée car problème antenne de
                télépéage à puissance réduite
                09h : commande terminée sur timeout de réponse de l’OBE
                1Dh : configuration non effectuée
            Response_T_APDU, variable:
        """
        message_content = bytes([0x06]) + t_apdu_containing_request
        response_content = self.send_command(message_content)
        # Removing Command ID 0x06
        self.t_apdu_containing_response = response_content[1:]
        return response_content

    def _pertel_change_config(self, config_parameters:bytes) -> bytes:
        """
        Request:
            Command ID, 1 byte:
                0x15
            BST, variable size:
        Response:
            Command ID, 1 byte:
                0x15
            Error, 1 byte:
            VST, variable size:
            """
        message_content = bytes([0x15]) + config_parameters
        response_content = self.send_command(message_content)

        return response_content

    def _pertel_read_version_and_config(self, t_apdu_containing_bst:bytes) -> bytes:
        """
        Request:
            Command ID, 1 byte:
                0x16
            BST, variable size:
        Response:
            Command ID, 1 byte:
                0x16
            Error, 1 byte:
            VST, variable size:
            """
        message_content = bytes([0x16]) + t_apdu_containing_bst
        response_content = self.send_command(message_content)

        return response_content

    def _pertel_emit_bst_and_get_vst_without_changing_beacon_id(self, t_apdu_containing_bst:bytes) -> bytes:
        """
        Request:
            Command ID, 1 byte:
                0x17
            BST, variable size:
        Response:
            Command ID, 1 byte:
                0x17
            Error, 1 byte:
            VST, variable size:
            """
        message_content = bytes([0x17]) + t_apdu_containing_bst
        response_content = self.send_command(message_content)

        # Removing Command ID 0x17
        self.t_apdu_containing_vst = response_content[1:]
        return response_content

    def _pertel_reset_beacon(self) -> bytes:
        """
        This command resets the communication and error counters!
        Request:
            Command ID, 1 byte:
                0x1E
            Identifier, 1 byte:
        Response:
            Command ID, 1 byte:
                0x1E
            Error, 1 byte:
            """
        message_content = bytes([0x1E])
        return self.send_command(message_content)
