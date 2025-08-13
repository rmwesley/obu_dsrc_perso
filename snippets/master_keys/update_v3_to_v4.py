import json
from Crypto.Cipher import DES3

def compute_master_key_kcv(master_key_bytes: bytes) -> str:
    return DES3.new(master_key_bytes, DES3.MODE_ECB).encrypt(bytearray(8))[:3].hex().upper()

with open('../security_info/toll_charging/master_keys_v3.0.0.json', 'r') as json_file:
    master_keysets = json.load(json_file)
    for keyset_name, master_keys in master_keysets.items():
        for key_ref, master_key_hex in master_keys.items():
            master_key_bytes = bytes.fromhex(master_key_hex)
            kcv = compute_master_key_kcv(master_key_bytes)

            mk_every_2_bytes_hex = [f'{byte1:02X}{byte2:02X}' for byte1, byte2 in zip(master_key_bytes[::2], master_key_bytes[1::2])]
            master_key_hex = ' '.join(mk_every_2_bytes_hex)
            master_key_with_kcv = {
                'mk_hex_value': master_key_hex,
                'kcv': kcv,
            }
            master_keys[key_ref] = master_key_with_kcv
with open('../security_info/toll_charging/master_keys_v4.0.0.json', 'w') as json_file:
    json.dump(master_keysets, json_file, indent=2)