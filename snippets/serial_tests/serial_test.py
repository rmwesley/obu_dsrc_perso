import serial

serial_instance = serial.Serial("COM1", baudrate=115200, parity="E", stopbits=2)
array = serial_instance.read(1)
print(array)