import json
import io
import serial
import logging
import threading

bac_serial_wrapper_logger = logging.getLogger(__name__)

with open('settings/beacon_manager_config.json', 'r') as beacon_manager_settings_file:
    beacon_manager_settings = json.load(beacon_manager_settings_file)
    chosen_beacon_name = beacon_manager_settings['default_beacon_name']
    bac_l2_config = beacon_manager_settings[chosen_beacon_name]['bac_l2_config']

def crc16_arc(data : bytearray) -> bytes:
    crc = 0
    for byte_val in data:
        crc ^= byte_val
        for j in range(8):
            if ((crc & 0x1) == 1):
                crc = int((crc / 2)) ^ 40961
            else:
                crc = int(crc / 2)
    crc16_int = crc & 0xFFFF
    crc_2_bytes = int.to_bytes(crc16_int, length=2, byteorder='little')
    return crc_2_bytes

def wrap_message(message_content:bytes) -> bytes:
    """Wrap message contents with control characters and append its CRC16 (Checksum) at the end"""
    message_frame = DLE + STX + message_content + DLE + ETX
    # We skip the first 2 bytes (DLE and STX) to compute the CRC-16 of the message!!
    crc16_bytes = crc16_arc(message_frame[2:])
    return message_frame + crc16_bytes

ENQ = bytes([0x05]) # Request the transmission of a message
ACK = bytes([0x06]) # Positive acknowledgement (message can be sent!!)
NAK = bytes([0x15]) # Negative acknowledgement (message CANNOT be sent!)
EOT = bytes([0x04]) # End Of Transmission of message
DLE = bytes([0x10]) # Escape character, to discriminate between special characters and message content
STX = bytes([0x02]) # Start of message
ETX = bytes([0x03]) # End of message

MAX_TRANSFER_REQ_RETRIES = 255
MAX_MSG_TRANSFER_RETRIES = 8

class BacHost(serial.SerialBase):
    def __init__(self, *args, **kwargs):
        """Initialize serial communication (inherited from SerialBase).
        We also initialized the message sender and receiver.

        Reminder:
        The serial port is opened here since we inherit from SerialBase!!
        The port SHOULD NOT be opened beforehand!

        Also, we do not implement a BAC L2 beacon serial port listener!
        As such, we only expect reading BAC L2 Rx in response to our commands!
        """
        bac_serial_wrapper_logger.info(f"Initializing BAC protocol L2 communication with beacon...!!")

        self._bac_l2_lock = threading.Lock()
        # Opening the serial port
        bac_serial_wrapper_logger.info(f"Initializing serial communication with beacon (from config data)...!!")
        serial_config = bac_l2_config['beacon_host_serial_config']
        super().__init__(*args, **serial_config, **kwargs)

        # T1 = 432.0 / self.baudrate
        T1 = 460.8 / self.baudrate
        self.TRANSFER_REQUEST_TIMEOUT = T1
        self.sender = BacMsgTransfer(self)
        self.receiver = BacMsgReceiver(self)

        bac_serial_wrapper_logger.info(f"Successfully initialized BAC protocol serial wrapper!")

    def send_command(self, message_content:bytes) -> bytes:
        self._transfer_message(message_content)
        return self._receive_message()

    # Host transfers a message
    def _transfer_message(self, message_content:bytes):
        self._bac_l2_lock.acquire()
        result = self.sender.transfer_message(message_content)
        self._bac_l2_lock.release()
        return result 

    # Host receives a message
    def _receive_message(self) -> bytes:
        self._wait_for_transfer_req_from_dest()

        self._bac_l2_lock.acquire()
        response = self.receiver.receive_message()
        self._bac_l2_lock.release()
        return response

    def _beacon_resolve_enq_conflict(self):
        self._send_request_to_transfer_msg_to_dest()

    def _host_resolve_enq_conflict(self):
        self._receive_message()

    def _send_request_to_transfer_msg_to_dest(self) -> bool:
        """Request sent from host to beacon to transfer a message.

        That is, the Host asks to be the source and the beacon the destination of a message.
        The Host thus sends an ENQ and waits for an ACK (with a timeout)"""
        received_char = b''

        # no_ack_count = 0
        transfer_request_counter = 0
        while received_char != ACK:
            # Contention (ENQ conflict) resolution for Host
            if received_char == ENQ:
                self._host_resolve_enq_conflict()
                return False
            if transfer_request_counter > MAX_TRANSFER_REQ_RETRIES:
                raise Exception('Maximum transfer request retries exceeded!!')
            self.write(ENQ)
            # Wait for ACK, with a timeout
            received_char = self.read(1, timeout=self.TRANSFER_REQUEST_TIMEOUT)
            transfer_request_counter += 1
        return True

    def _wait_for_transfer_req_from_dest(self) -> bool:
        received_char = self.read(1)
        if received_char != ENQ:
            raise Exception('Received non-ENQ character before transaction started!!')
        # Got an ENQ from destination!
        self.write(ACK)
        return True

class BacMsgTransfer(io.RawIOBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        T1 = 460.8 / self.baudrate
        self.TRANSFER_REQUEST_TIMEOUT = T1

    def _msg_ack_received_from_dest(self) -> bool:
        """Wait for an ACK from dest after sending a message (with a timeout)"""
        received_char = self.read(1, self.TRANSFER_REQUEST_TIMEOUT)
        if received_char == NAK:
            return False
        elif received_char != ACK:
            return False
        else:
            raise Exception('Invalid control character received during message transfer!!!')
        return True

    # Source transfers a message to destination
    def transfer_message(self, message_content:bytes):
        message_value = wrap_message(message_content)
        self.write(message_value)

        message_transfer_counter = 0
        # Reemit message until ACK is received!
        while not self._msg_ack_received_from_dest():
            if message_transfer_counter > MAX_MSG_TRANSFER_RETRIES:
                raise Exception('Exceeded message transfer retry limit!!')
            self.write(message_value)
            message_transfer_counter += 1

        self.write(EOT)

    def transfer_and_receive_message(self, message_content:bytes) -> bytes:
        self.transfer_message(message_content)
        return self.read_message()

class BacMsgReceiver(io.RawIOBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        T2 = 384 / self.baudrate
        self.MESSAGE_CHARACTER_READ_TIMEOUT = T2

    def _handle_repeated_transfer_requests(self, received_char):
        """Handles cases in which ACK for message transfer request was lost by source.
        That is, the source sent an ENQ again."""
        transfer_request_counter = 0
        while received_char == ENQ:
            # ACK was lost by the source!!!
            if transfer_request_counter > MAX_TRANSFER_REQ_RETRIES - 1:
                raise Exception('Maximum transfer request retries exceeded!!')
            self.write(ACK)
            received_char = self.read(1)
            transfer_request_counter += 1
        return received_char
    def _wait_for_message_start_header(self):
        received_char = self.read(1)
        first_char = self._handle_repeated_transfer_requests(received_char)

        if first_char != DLE:
            raise Exception(f'Message did not start with DLE/STX control sequence!!: 0x{first_char.hex().upper()}')
        second_char = self.read(1)
        if second_char != STX:
            control_sequence = bytes.join(first_char, second_char)
            raise Exception(f'Message did not start with DLE/STX control sequence!!: 0x{control_sequence.hex().upper()}')
        return True

    def read_message_content_and_acknowledge_it(self) -> bytes:
        """Read message content and acknowledge it!
        We read bytes until we get to the control sequence DLE/ETX"""
        source_msg_content = bytearray()
        current_char = b''
        # Escaped character!!
        while current_char != DLE:
            current_char = self.read(1)
            # End of message control sequence!!
            if current_char == ETX:
                break
            source_msg_content.append(current_char[0])

        self.write(ACK)

        return source_msg_content

    def receive_message(self):
        self._wait_for_message_start_header()
        source_msg_content = self.read_message_content()
        return source_msg_content