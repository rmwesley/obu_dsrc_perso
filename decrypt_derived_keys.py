from key_derivation import decrypt_access_key, decrypt_auth_key
import logging
logging.basicConfig(level=logging.DEBUG)

efc_cm = "C04001F200A6"
decrypt_access_key(efc_cm, bytes.fromhex("82E330789B8A6284"))
decrypt_auth_key(efc_cm, bytes.fromhex("EBE97F200C853299"), 118)
decrypt_auth_key(efc_cm, bytes.fromhex("82287E9CA265A240"), 118)
decrypt_auth_key(efc_cm, bytes.fromhex("6ED8F70749FD21B9"), 117)