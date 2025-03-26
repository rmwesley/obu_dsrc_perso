# CountryCode is encoded with ITA2 (or Baudot) encoding
import baudot
from io import BytesIO, BufferedIOBase

import baudot.handlers

country_code = 0xb280

first_5bits = (country_code >> 11) & 0b11111
second_5bits = (country_code >> 6) & 0b11111

def reverse_mask_5_bits(x:int) -> int:
    x = ((x & 0x05) << 1) | ((x & 0x0A) >> 1) | (x & 0x10)
    x = ((x & 0x03) << 2) | ((x & 0x0C) >> 2) | (x & 0x10)
    x = ((x & 0x0F) << 1) | ((x & 0x10) >> 4)
    return x

class ReadError(Exception):
     pass
class BaudotMsbFirstBytesReader(baudot.handlers.core.BaudotReader):
    def __init__(self, stream: BufferedIOBase):
        self.stream = stream

    def __next__(self):
        next_byte = self.stream.read(1)
        if not next_byte:
            raise StopIteration()
        try:
            code = next_byte[0]
            code = reverse_mask_5_bits(code)
        except ValueError:
            str_repr = next_byte.decode(errors='backslashreplace')
            raise ReadError(f'Invalid hexadecimal byte: {str_repr}')
        if not 0 <= code < 32:
            raise ReadError(f'Code value {code} is not a valid 5-bit value')
        print(code)
        return code

baudot_2_bytes_int = int.from_bytes([first_5bits, second_5bits])
print(f'0xB280 10 MSB split in 2 bytes, 5 bits each: {baudot_2_bytes_int:0b}')

# baudot_lsb_on_right = [reverse_mask_1_byte(curr_int) for curr_int in [first_5bits, second_5bits]]
baudot_lsb_on_right = bytes([13, 10])
baudot_lsb_on_right = [first_5bits, second_5bits]

# ITA2_SWITCH_CODE = 0x1F
code = bytes([0x1F]) + bytes(baudot_lsb_on_right)
print(f"Baudot code with LSB on the right, split in bytes, in hex: {code.hex()}")
with BytesIO(code) as country_code_bitstream:
        reader = BaudotMsbFirstBytesReader(country_code_bitstream)
        country_code_str = baudot.decode_to_str(reader, baudot.codecs.ITA2_STANDARD)
print(country_code_str)