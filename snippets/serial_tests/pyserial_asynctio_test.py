import asyncio
import serial.serialutil
import serial_asyncio
import threading
import time
import serial
import traceback

class InputChunkProtocolClass(asyncio.Protocol):
    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        print(f'Data received: {repr(data)}')
        # self._serial.read(1)

        # stop callbacks again immediately
        self.pause_reading()

    def pause_reading(self):
        # This will stop the callbacks to data_received
        self.transport.pause_reading()

    def resume_reading(self):
        # This will start the callbacks to data_received again with all data that has been received in the meantime.
        self.transport.resume_reading()

async def initialization() -> tuple[serial_asyncio.SerialTransport, asyncio.StreamReaderProtocol]:
    global transport
    global protocol
    global reading_loop

    if 'transport' not in globals() and 'protocol' not in globals():
        # serial_async_event_loop = asyncio.new_event_loop()
        transport, protocol = await serial_asyncio.create_serial_connection(reading_loop, InputChunkProtocolClass, 'COM13', baudrate=115200)
        print('Initialized serial communication!')
    # else:
    #     print('Already initialized!!')

    return transport, protocol

async def reader():
    transport, protocol = await initialization()
    while True:
        await asyncio.sleep(0.3)
        print('Trying to read data!')
        protocol.resume_reading()
        # result = protocol.transport._serial.read(1)
        # print(result)

async def write(bytestream:bytes):
    transport, protocol = await initialization()

    await asyncio.sleep(1)
    transport.write(bytestream)
    print(f'Wrote {bytestream}')

def continuous_reading():
    global reading_loop

    reading_loop = asyncio.new_event_loop()
    reading_loop.run_until_complete(reader())
    print('Closing reading loop!')
    reading_loop.close()

continuous_reading = threading.Thread(target=continuous_reading, daemon=True)
continuous_reading.start()

writing_loop = asyncio.new_event_loop()
time.sleep(0.3)
writing_loop.run_until_complete(write(b'\x01'))


time.sleep(0.3)
writing_loop.run_until_complete(write(b'\x02'))

time.sleep(0.3)
writing_loop.run_until_complete(write(b'\x64'))
time.sleep(3)
writing_loop.close()
time.sleep(100)