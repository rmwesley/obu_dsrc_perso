from efc_security import efc_key_derivation
from toll_charging_security import tc_dsrc_auth

pan_bytes = bytes.fromhex('3156490000050015258F')
compact_pan = efc_key_derivation.compute_compact_pan(pan_bytes)

print(f'Compact PAN: {compact_pan.hex().upper()}')

efc_cm = 'B28031000871'
auk_value_bytes = efc_key_derivation.compute_auk_plaintext(pan_bytes, efc_cm)
print(auk_value_bytes.hex())

attribute_list_bytes = b'\x01 @1VI\x00\x00\x05\x00\x15%\x8fZ\x7f\x00\x00'
rnd_rse = 1182356587

manufacturer_id = '0029'
equipment_class = '0101'
obu_contract_ref = f'{efc_cm}{manufacturer_id}{equipment_class}'
result = tc_dsrc_auth.compute_authenticator_with_device_contract_ref_and_auk_ref(pan_bytes, obu_contract_ref, attribute_list_bytes, rnd_rse, auk_ref=111)
# result = dsrc_security.authenti(pan_bytes, efc_cm, attribute_list_bytes, rnd_rse, auk_ref=111)

print(efc_key_derivation.force_compute_auk_with_efc_cm_and_auk_ref_only(pan_bytes, efc_cm, 111).hex())
print(f'Attr Auth from MasterKey: {result.hex().upper()}')

auk_value = bytes.fromhex('5A84DE9D99EC6133')
result = tc_dsrc_auth.compute_authenticator_with_auk_value(attribute_list_bytes, rnd_rse, auk_value)
print(f'Attr Auth with personalized key: {result.hex().upper()}')