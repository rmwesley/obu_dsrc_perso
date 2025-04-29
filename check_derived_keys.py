from dsrc_key_derivation import decrypt_access_key, decrypt_auth_key
import logging
logging.basicConfig(level=logging.DEBUG)

efc_cm = "C04001F200A6"
print(f"Correct keys:")
decrypt_access_key(efc_cm, bytes.fromhex("82E330789B8A6284"))
decrypted_auk = decrypt_auth_key(efc_cm, bytes.fromhex("EBE97F200C853299"), 118)
print(f"Decrypted AuK: {decrypted_auk.hex().upper()}\n\n")


logging.error("WRONG Contract Provider used in key derivation, so keys are wrong:")
print()
decrypt_auth_key(efc_cm, bytes.fromhex("82287E9CA265A240"), 118)
decrypt_auth_key(efc_cm, bytes.fromhex("6ED8F70749FD21B9"), 117)
decrypt_auth_key(efc_cm, bytes.fromhex("82287E9CA265A240"), 111)