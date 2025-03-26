# CountryCode is encoded with ITA2 (or Baudot) encoding
import baudot
from io import BytesIO

code = b'1f160a'
code = b'1f0d0a'

country_code = 0xb280

first_5bits = (country_code >> 11) & 0b11111
second_5bits = (country_code >> 6) & 0b11111

# First, we invert the bits
print('{:b}'.format(first_5bits).zfill(5))
# print('{:b}'.format(first_5bits).zfill(5)[::-1])
print('{:b}'.format(second_5bits).zfill(5))

cc = bytes([
        int('{:b}'.format(first_5bits).zfill(5)[::-1], 2),
        int('{:b}'.format(second_5bits).zfill(5)[::-1], 2)]
        )

print(cc.hex())

code = b'1f' + cc.hex().encode('utf-8')

print(code)
with BytesIO(code) as country_code_bitstream:
        reader = baudot.handlers.HexBytesReader(country_code_bitstream)
        country_code_str = baudot.decode_to_str(reader, baudot.codecs.ITA2_STANDARD)

print(country_code_str)