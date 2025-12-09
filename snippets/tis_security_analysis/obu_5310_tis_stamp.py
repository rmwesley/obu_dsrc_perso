from dsrc_security import dsrc_key_derivation
from toll_charging_security import tc_td_key_derivation, tc_dsrc_auth

pan_bytes = bytes.fromhex('3156496003462003536F')
compact_pan = dsrc_key_derivation.compute_compact_pan(pan_bytes)

print(f'Compact PAN: {compact_pan.hex().upper()}')

# Derived Keys (Personalization)
efc_cm = 'B28031000779'
plaintext_bytes = dsrc_key_derivation.compute_auk_plaintext(pan_bytes, efc_cm, norm='TIS_decimal')
mauk_111_hex_str = '9F60 25DE 0A64 58CB 2EFC 071F E343 24D8'
mauk_111_bytes = bytes.fromhex(mauk_111_hex_str)
auk_bytes = dsrc_key_derivation.compute_auk_with_mauk_value_and_plaintext(plaintext_bytes, mauk_111_bytes)

print(f'Computed AuK from MK: {auk_bytes.hex().upper()}')

gescom_auk1_bytes = bytes.fromhex('609BCE034829029A')
print(f'AuK1 provided by GESCOM: {gescom_auk1_bytes.hex().upper()}')

# Attribute authenticator (DSRC communication, OBE <> RSE)
attribute_list_bytes = b'\x01 @1VI\x00\x00\x05\x00\x15%\x8fZ\x7f\x00\x00'
rnd_rse = 1182356587

manufacturer_id = '0003'
equipment_class = '7403'
obu_contract_ref = f'{efc_cm}{manufacturer_id}{equipment_class}'
result = tc_dsrc_auth.compute_authenticator_with_device_contract_ref_and_auk_ref(pan_bytes, obu_contract_ref, attribute_list_bytes, rnd_rse, auk_ref=111, norm='TIS_decimal')
# result = dsrc_security.authenti(pan_bytes, efc_cm, attribute_list_bytes, rnd_rse, auk_ref=111)

print(tc_td_key_derivation.force_compute_auk_with_efc_cm_and_auk_ref_only(pan_bytes, efc_cm, 111, norm='TIS_decimal').hex())
print(f'Attr Auth from MasterKey: {result.hex().upper()}')

result = tc_dsrc_auth.compute_authenticator_with_auk_value(attribute_list_bytes, rnd_rse, gescom_auk1_bytes)
print(f'Attr Auth with personalized key: {result.hex().upper()}')