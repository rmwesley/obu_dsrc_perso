from Crypto.Cipher import DES, DES3

def compute_access_credentials_with_8_bytes_uset_key(rnd_obe:int, uset_derived_key) -> bytes:
    # Prepare the DES cipher with the derivec Access Key/USET Key
    cipher = DES.new(uset_derived_key, DES.MODE_ECB)
    # The padding is automatically added to the right of RndOBE for DES
    # We add 4 bytes of padding to the right of RndOBE
    output = cipher.encrypt(rnd_obe.to_bytes(4) + bytearray(4))

    # We now truncate this output to the 4 left-most bytes
    ac_cr = output[:4]
    return ac_cr

def compute_access_credentials_with_16_bytes_uset_key(rnd_obe:int, uset_derived_key) -> bytes:
    # print(uset_derived_key)
    cipher = DES3.new(uset_derived_key, DES3.MODE_ECB)
    output = cipher.encrypt(rnd_obe.to_bytes(4) + bytearray(4))

    ac_cr = output[:4]
    return ac_cr
compute_access_credentials_with_32_bytes_uset_key = compute_access_credentials_with_16_bytes_uset_key

def compute_access_credentials_with_uset_key(rnd_obe:int, uset_derived_key) -> bytes:
    if len(uset_derived_key) == 8:
        uset_ac_cr = compute_access_credentials_with_8_bytes_uset_key(rnd_obe, uset_derived_key)
    if len(uset_derived_key) == 16:
        uset_ac_cr = compute_access_credentials_with_16_bytes_uset_key(rnd_obe, uset_derived_key)
    if len(uset_derived_key) == 32:
        uset_ac_cr = compute_access_credentials_with_32_bytes_uset_key(rnd_obe, uset_derived_key)
    return uset_ac_cr
