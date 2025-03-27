import json
import serial
import logging
import asyncio

bac_serial_wrapper_logger = logging.getLogger(__name__)

class BacL2Exception(Exception):
    pass

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

ENQ = bytes([0x05]) # Request the transmission of a message
ACK = bytes([0x06]) # Positive acknowledgement (message can be sent!!)
NAK = bytes([0x15]) # Negative acknowledgement (message CANNOT be sent!)
EOT = bytes([0x04]) # End Of Transmission of message
DLE = bytes([0x10]) # Escape character, to discriminate between special characters and message content
STX = bytes([0x02]) # Start of message
ETX = bytes([0x03]) # End of message

MAX_TRANSFER_REQ_RETRIES = 255
MAX_MSG_TRANSFER_RETRIES = 8

T1_FOR_1_BAUD = 20000
T2_FOR_1_BAUD = 20000

def escape_dle_in_message_content(message_content:bytes) -> bytes:
    escaped_message_content = bytearray()
    for char_int in message_content:
        if char_int == DLE[0]:
            # Add an escape character!
            escaped_message_content.append(DLE[0])
        escaped_message_content.append(char_int)
    return escaped_message_content

def wrap_message(message_content:bytes) -> bytes:
    """
    We escape DLE (0x10) characters in the message content and then
    wrap the message content with start and end control characters,
    appending its CRC16 (Checksum) at the end.
    """
    # Escape DLE (0x10) characters
    escaped_message_content = escape_dle_in_message_content(message_content)
    # Wrap message with control chars
    message_frame = DLE + STX + escaped_message_content + DLE + ETX
    # Then we append its CRC-16 checksum at the end
    # We skip the first 2 bytes (DLE and STX) to compute the CRC-16 of the message!!
    crc16_bytes = crc16_arc(message_frame[2:])

    return message_frame + crc16_bytes

def unescape_dle_in_message_content(message_content:bytes) -> bytes:
    unescaped_message_content = bytearray()
    escape_next = False
    for char_int in message_content:
        if escape_next:
            if char_int == DLE[0]:
                unescaped_message_content.append(char_int)
                escape_next = False
            else:
                raise BacL2Exception(f'Forgot to escape DLE, or escaped (0x{char_int}), a non-DLE (0x10) character !')
            continue
        elif char_int == DLE[0]:
            escape_next = True
            continue
        unescaped_message_content.append(char_int)
    return unescaped_message_content

# Default values are empty Queues instead of None!!
# We will use this to get one response queue per Command ID
class MessageQueuesDict(dict):
    def __getitem__(self, key) -> asyncio.Queue:
        if key not in self:
            dict.__setitem__(self, key, asyncio.Queue())
        return dict.__getitem__(self, key)

# Remember to increase the timeouts if you are sniffing the serial line!!
# Otherwise, use the values set above
# T1_FOR_1_BAUD = 20000
# T2_FOR_1_BAUD = 20000
class BacHost(serial.Serial):
    def __init__(self, *args, **kwargs):
        """Initialize serial communication (inherited from SerialBase).
        We also initialized the message sender and receiver.

        Reminder:
        The serial port is opened here since we inherit from SerialBase!!
        The port SHOULD NOT be opened beforehand!

        Also, we do not implement a BAC L2 beacon serial port listener!
        As such, we only expect reading BAC L2 Rx in response to our commands!
        """
        bac_serial_wrapper_logger.debug(f"Initializing BAC protocol L2 communication with beacon...!!")

        # Opening the serial port
        bac_serial_wrapper_logger.info(f"Initializing serial communication (BAC L1) with beacon (from config data)...!!")
        serial_config = bac_l2_config['beacon_host_serial_config']
        # print(f'Serial config: {serial_config}')
        super().__init__(*args, **serial_config, **kwargs)

        T1 = T1_FOR_1_BAUD / self.baudrate
        self.TRANSFER_REQUEST_TIMEOUT = T1
        self.sender = BacMsgTransfer(serial_instance=self)
        self.receiver = BacMsgReceiver(serial_instance=self)

        bac_serial_wrapper_logger.info(f"Successfully initialized BAC L2 (serial protocol) handler!")

        self.async_message_loop = asyncio.new_event_loop()
        # Queue of responses awaiting to be gotten by the respective callers.
        # I made this a queue so requests can await for their respective response to arrive.
        self.async_response_queue_dict_by_command_id = MessageQueuesDict()

    async def send_command(self, message_content:bytes) -> bytes:
        return await self.send_command_and_await_response(message_content)

    def send_command_and_block_until_response(self, message_content:bytes) -> bytes:
        future = self.send_command_and_await_response(message_content)
        response_content = self.async_message_loop.run_until_complete(future)
        return response_content

    async def send_command_and_await_response(self, message_content:bytes) -> None:
        """Send message and await a response from Beacon"""
        command_id = message_content[0]
        command_queue = self.async_response_queue_dict_by_command_id[command_id]

        self._send_request_message(message_content)
        await self.__block_and_receive_response_message(command_id)

        response_content = await command_queue.get()
        return response_content

    def _send_request_message(self, message_content:bytes) -> asyncio.Queue:
        """Send a message to beacon.
        That is, a request from Host to Beacon."""
        command_id = message_content[0]

        if self._send_request_to_transfer_msg_to_dest():
            self._transfer_message(message_content)

    # DEPRECATION WARNING
    async def __block_and_receive_response_message(self, command_id:int):
        """Default is no timeout.

        timeout=0 is immediate.
        timeout=None is blocking behavior!

        BAC L2 is an asynchronous protocol.
        We can send multiple commands at once (Async I/O).
        Using a blocking function is not ideal.
        We should do periodic response polling instead and resolve a Future-like object"""
        response_queue = self.async_response_queue_dict_by_command_id[command_id]

        response_content = b''
        if self.__block_and_wait_for_transfer_req_from_dest():
            response_content = self._receive_message()

        await response_queue.put(response_content)

    # Host transfers a message
    def _transfer_message(self, message_content:bytes):
        result = self.sender.transfer_message(message_content)
        return result

    # Host receives a message
    def _receive_message(self) -> bytes:
        unescaped_response_content = self.receiver.receive_message()
        return unescaped_response_content

    def _beacon_resolve_enq_conflict(self):
        self._send_request_to_transfer_msg_to_dest()

    def _host_resolve_enq_conflict(self):
        self.write(ACK)
        self._receive_message()

    def _send_request_to_transfer_msg_to_dest(self) -> bool:
        """Request sent from host to beacon to transfer a message.

        That is, the Host asks to be the source and the beacon the destination of a message.
        The Host thus sends an ENQ and waits for an ACK (with a timeout)"""
        # Setting timeout to T1!
        self.timeout = self.TRANSFER_REQUEST_TIMEOUT

        received_char = b''

        # no_ack_count = 0
        transfer_request_counter = 0
        while received_char != ACK:
            # Contention (ENQ conflict) resolution for Host
            if received_char == ENQ:
                self._host_resolve_enq_conflict()
                return False
            if transfer_request_counter > MAX_TRANSFER_REQ_RETRIES:
                raise BacL2Exception('Maximum transfer request retries exceeded!!')
            self.write(ENQ)
            # Wait for ACK, with the timeout TRANSFER_REQUEST_TIMEOUT
            received_char = self.read(1)
            transfer_request_counter += 1
        return True

    def read_with_timeout(self, size:int, timeout:float):
        previous_timeout_value = self.timeout
        self.timeout = timeout
        received_char = self.read(size)
        self.timeout = previous_timeout_value
        return received_char

    # DEPRECATION WARNING
    def __block_and_wait_for_transfer_req_from_dest(self):
        """Blocking wait function to read 1 byte.
        That is, no timeout=None!"""
        received_char = self.read_with_timeout(1, timeout=None)
        if received_char == b'':
            raise BacL2Exception('Received null byte! Set timeout to None!!!')
        elif received_char == EOT:
            print('[BAC L2] Received EOT instead of ENQ!! A message was lost!')
            return False
        elif received_char != ENQ:
            raise BacL2Exception(f'Received non-ENQ character ({received_char.hex().upper()}) before reception started!!')
        # Got an ENQ from destination!
        self.write(ACK)
        return True
    def close(self):
        super().close()
        self.async_message_loop.close()

class BacMsgTransfer():
    def __init__(self, serial_instance: serial.Serial):
        T1 = T1_FOR_1_BAUD / serial_instance.baudrate
        self.TRANSFER_REQUEST_TIMEOUT = T1
        self.serial_instance = serial_instance

    def _msg_ack_received_from_dest(self) -> bool:
        """Wait for an ACK from dest after sending a message (with a timeout)"""
        # Setting timeout to T1!
        self.serial_instance.timeout = self.TRANSFER_REQUEST_TIMEOUT

        received_char = self.serial_instance.read(1)
        if received_char == ACK:
            return True
        if received_char == NAK:
            return False
        if received_char == b'':
            # Read timed out after T1 seconds elapsed!!
            return False
        else:
            raise BacL2Exception(f'Invalid control character ({received_char.hex().upper()}) received during message transfer!!!')

    # Source transfers a message to destination
    def transfer_message(self, message_content:bytes):
        print(f'[BAC L2] Sending message content...: 0x{message_content.hex().upper()}')

        message_value = wrap_message(message_content)
        # print(f'[BAC L2] Sent message content with STX: {message_value.hex().upper()}')
        self.serial_instance.write(message_value)

        message_transfer_counter = 0
        # Reemit message until ACK is received!
        while not self._msg_ack_received_from_dest():
            if message_transfer_counter > MAX_MSG_TRANSFER_RETRIES:
                raise BacL2Exception('Exceeded message transfer retry limit!!')
            self.serial_instance.write(message_value)
            message_transfer_counter += 1

        self.serial_instance.write(EOT)

    def transfer_and_receive_message(self, message_content:bytes) -> bytes:
        self.transfer_message(message_content)
        return self.read_message()

class BacMsgReceiver():
    def __init__(self, serial_instance: serial.Serial):
        T1 = T1_FOR_1_BAUD / serial_instance.baudrate
        T2 = T2_FOR_1_BAUD / serial_instance.baudrate

        self.TRANSFER_REQUEST_TIMEOUT = T1
        self.MESSAGE_CHARACTER_READ_TIMEOUT = T2
        self.EOT_CHAR_TIMEOUT = T1 + T2

        self.serial_instance = serial_instance

    def _handle_repeated_transfer_requests(self, received_char):
        """Handles cases in which ACK for message transfer request was lost by source.
        That is, the source sent an ENQ again."""
        transfer_request_counter = 0
        while received_char == ENQ:
            # ACK was lost by the source!!!
            if transfer_request_counter > MAX_TRANSFER_REQ_RETRIES - 1:
                raise BacL2Exception('Maximum transfer request retries exceeded!!')
            self.serial_instance.write(ACK)
            received_char = self.serial_instance.read(1)
            transfer_request_counter += 1
        return received_char

    def _wait_for_message_start_header(self):
        received_char = self.serial_instance.read(1)
        first_char = self._handle_repeated_transfer_requests(received_char)

        if first_char != DLE:
            raise BacL2Exception(f'Message did not start with DLE/STX control sequence!!: 0x{first_char.hex().upper()}')
        second_char = self.serial_instance.read(1)
        if second_char != STX:
            control_sequence = bytes.join(first_char, second_char)
            raise BacL2Exception(f'Message did not start with DLE/STX control sequence!!: 0x{control_sequence.hex().upper()}')
        # print('[BAC L2] Message start control sequence DLE/STX received!!')
        return True

    def _check_received_msg_crc(self, message_content, crc_bytes) -> bool:
        # print(f'[BAC L2] CRC-16: 0x{crc16_arc(message_content).hex()}')
        return crc_bytes == crc16_arc(message_content)

    def _read_message_content_and_acknowledge_it(self) -> bytes:
        """Read message content and acknowledge it!
        We read bytes until we get to the control sequence DLE/ETX"""
        received_msg_content_with_etx = bytearray()
        current_char = b''
        while current_char != DLE + ETX:
            # Non-escaped character!
            if current_char != DLE:
                current_char = self.serial_instance.read(1)
                received_msg_content_with_etx.append(current_char[0])
            # Escaped character!!
            if current_char == DLE:
                current_char = self.serial_instance.read(1)
                received_msg_content_with_etx.append(current_char[0])
                # End of message control sequence!!
                if current_char == ETX:
                    break
        crc_bytes = self.serial_instance.read(1) + self.serial_instance.read(1)
        # print(f"[BAC L2] Response from beacon with ETX: 0x{received_msg_content_with_etx.hex().upper()}")

        if self._check_received_msg_crc(received_msg_content_with_etx, crc_bytes):
            self.serial_instance.write(ACK)
        else:
            self.serial_instance.write(NAK)
            self.receive_message()

        received_msg_content = received_msg_content_with_etx[:-2]
        # print(f"[BAC L2] Response from beacon: 0x{received_msg_content.hex().upper()}")

        return received_msg_content_with_etx

    def _receive_eot_char(self):
        self.serial_instance.timeout = self.EOT_CHAR_TIMEOUT

        received_char = self.serial_instance.read(1)
        if received_char == EOT:
            return True
        raise BacL2Exception(f'Received non-EOT char ({received_char}) after end of message reception!!')

    def receive_message(self):
        self._wait_for_message_start_header()
        source_msg_content_with_etx = self._read_message_content_and_acknowledge_it()
        unescaped_source_msg_content = unescape_dle_in_message_content(source_msg_content_with_etx[:-2])
        print(f'[BAC L2] Received message content: 0x{unescaped_source_msg_content.hex().upper()}')

        self._receive_eot_char()

        return unescaped_source_msg_content