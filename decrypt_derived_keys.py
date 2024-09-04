from key_derivation import decrypt_access_key
import logging
logging.basicConfig(level=logging.DEBUG)

decrypted_ciphertext = decrypt_access_key("C04001F200A6", bytes.fromhex("82E330789B8A6284"))
print(decrypted_ciphertext.hex().upper())