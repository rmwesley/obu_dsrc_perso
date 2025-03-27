# CountryCode is encoded with ITA2 (or Baudot) encoding
import baudot
from io import BytesIO, BufferedIOBase

from custom_its_per_decoders import decode_country_code_from_int, decode_country_code_from_hex_str

country_code = 0xb280 >> 6

print(decode_country_code_from_int(country_code))
print(decode_country_code_from_hex_str('B280'))
print(decode_country_code_from_hex_str('B28'))