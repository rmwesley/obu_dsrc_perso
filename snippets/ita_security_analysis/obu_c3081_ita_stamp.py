from dsrc_security import dsrc_key_derivation
from toll_charging_security import tc_td_key_derivation, tc_dsrc_auth

pan_bytes = bytes.fromhex('3156496000613004264F')
compact_pan = dsrc_key_derivation.compute_compact_pan(pan_bytes)

print(f'Compact PAN: {compact_pan.hex().upper()}')

# Derived Keys (Personalization)
efc_cm = 'B28031000A75'
plaintext_bytes = dsrc_key_derivation.compute_auk_plaintext(pan_bytes, efc_cm, norm='EN15509')
mauk_111_hex_str = 'A6B5 7FC2 D327 F348 F6E2 5842 8E94 DCE0'
mauk_111_bytes = bytes.fromhex(mauk_111_hex_str)
auk_bytes = dsrc_key_derivation.compute_auk_with_mauk_value_and_plaintext(plaintext_bytes, mauk_111_bytes)

print(f'Computed AuK from MK: {auk_bytes.hex().upper()}')

gescom_auk1_bytes = bytes.fromhex('3691A11F26C12D81')
print(f'AuK1 provided by GESCOM: {gescom_auk1_bytes.hex().upper()}')

# Attribute authenticator (DSRC communication, OBE <> RSE)
# attribute_list_bytes = b'\x01 @1VI\x00\x00\x05\x00\x15%\x8fZ\x7f\x00\x00'
payment_means_hex = '31 56 49 60 00 61 30 04 26 4F 5A BF 00 00'
rnd_rse_hex = 'D082836D' # 3498214253

attribute_list_bytes = bytes.fromhex(payment_means_hex)
rnd_rse = int(rnd_rse_hex, 16)

manufacturer_id = '0007'
equipment_class = '5113'
obu_contract_ref = f'{efc_cm}{manufacturer_id}{equipment_class}'
result = tc_dsrc_auth.compute_authenticator_with_device_contract_ref_and_auk_ref(pan_bytes, obu_contract_ref, attribute_list_bytes, rnd_rse, td_name='IT_CEN', norm='EN15509', auk_ref=111)
# result = dsrc_security.authenti(pan_bytes, efc_cm, attribute_list_bytes, rnd_rse, auk_ref=111)

print(tc_td_key_derivation.force_compute_auk_with_efc_cm_and_auk_ref_only(pan_bytes, efc_cm, 111, td_name='IT_CEN', norm='EN15509').hex())
print(f'Attr Auth from MasterKey: {result.hex().upper()}')

result = tc_dsrc_auth.compute_authenticator_with_auk_value(attribute_list_bytes, rnd_rse, gescom_auk1_bytes)
print(f'Attr Auth with personalized key: {result.hex().upper()}')