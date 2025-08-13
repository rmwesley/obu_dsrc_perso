import json
from Crypto.Cipher import DES3

def compute_master_key_kcv(master_key_hex: str) -> str:
    master_key = bytes.fromhex(master_key_hex)
    return DES3.new(master_key, DES3.MODE_ECB).encrypt(bytearray(8))[:3].hex().upper()

with open('../security_info/toll_charging/master_keys_v3.0.0.json', 'r') as json_file:
    master_keysets = json.load(json_file)
    for keyset_name, master_keys in master_keysets.items():
        for key_ref, master_key_hex in master_keys.items():
            kcv = compute_master_key_kcv(master_key_hex)
            master_key_with_kcv = {
                'mk_hex_value': master_key_hex,
                'kcv': kcv,
            }
            master_keys[key_ref] = master_key_with_kcv
with open('../security_info/toll_charging/master_keys_v4.0.0.json', 'w') as json_file:
    json.dump(master_keysets, json_file, indent=2)