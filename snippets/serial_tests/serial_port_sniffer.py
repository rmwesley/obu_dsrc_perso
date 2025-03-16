import asyncio
from serial_asyncio import open_serial_connection
import serial_asyncio
import time
import threading
import os

# Reading data from a serial port.
# This is a coroutine running in an infinite loop, awaiting and relaying one line at a time.
async def relay_one_stream(stream_reader: asyncio.StreamReader, stream_writer: asyncio.StreamWriter):
    """Forwards or equivalently relays one stream from a COM Rx to a COM Tx"""
    while True:
        read_line_coroutine = await stream_reader.readline()
        print(f"Received bytes data!: {read_line_coroutine}")

        stream_writer.write(read_line_coroutine)

def indefinitely_forward_rx_to_tx(asyncio_loop: asyncio.AbstractEventLoop, in_stream_reader: asyncio.StreamReader, out_stream_writer: asyncio.StreamWriter):
    """Indefinitely awaits and forwards/relays streams from a COM Rx to a COM Tx"""
    stream_fwd_coroutine = relay_one_stream(stream_reader=in_stream_reader, stream_writer=out_stream_writer)

    l2r_fwd_thread = threading.Thread(target=asyncio_loop.run_until_complete, args=[stream_fwd_coroutine], daemon=True)
    l2r_fwd_thread.start()

def indefinitely_forward_dtr(in_serial_transport: serial_asyncio.SerialTransport, out_serial_transport: serial_asyncio.SerialTransport):
    out_serial_transport.serial.dtr = in_serial_transport.serial.dtr

l2r_com_port_loop = asyncio.new_event_loop()
l_reader, l_writer = l2r_com_port_loop.run_until_complete(
    open_serial_connection(url='COM6', baudrate=115200, parity='E', stopbits=2, limit=256)
)

r2l_com_port_loop = asyncio.new_event_loop()
r_reader, r_writer = r2l_com_port_loop.run_until_complete(
    open_serial_connection(url='COM14', baudrate=115200, parity='E', stopbits=2, limit=256)
)


# Plugging each Rx to Tx
indefinitely_forward_rx_to_tx(asyncio_loop=l2r_com_port_loop, in_stream_reader=l_reader, out_stream_writer=r_writer)
time.sleep(0.01)
indefinitely_forward_rx_to_tx(asyncio_loop=r2l_com_port_loop, in_stream_reader=r_reader, out_stream_writer=l_writer)
time.sleep(0.01)

# Plugging DTR to DTR
indefinitely_forward_dtr(l_writer.transport, r_writer.transport)
time.sleep(0.01)

time.sleep(3000)