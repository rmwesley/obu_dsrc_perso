from ASN.compiled_DSRC_instances import CCCv4_1 as EFC
import datetime
import custom_its_per_decoders

EFC.EfcCcc.CccContainer.from_uper(bytes.fromhex("6301676033AC0300CC144C0321339800676033413300CC14FD032133E86760337A67603D53"))

print(EFC.EfcCcc.CccContainer.to_asn1())
print(EFC.EfcCcc.CccContainer._val[1]['position'])

attr_99_jval = EFC.EfcCcc.CccContainer._to_jval()

utc_ts = attr_99_jval['extendedObeStatusHistoryPart1']['timeWhenChanged']
print(datetime.datetime.fromtimestamp(utc_ts, datetime.UTC))

def ugly_decode_jer_absolute_position_2d(absolute_position_2d):
    return {key : ugly_decode_jer_geodata_lat_long(value) for key, value in absolute_position_2d.items()}

ugly_decode_jer_geodata_lat_long = custom_its_per_decoders.decode_jer_dsrc_wgs_84_lat_long

longitude = attr_99_jval['extendedObeStatusHistoryPart1']['position']['gnssLon']
latitude = attr_99_jval['extendedObeStatusHistoryPart1']['position']['gnssLat']

longitude_str = ugly_decode_jer_geodata_lat_long(longitude)
latitude_str = ugly_decode_jer_geodata_lat_long(latitude)

print(latitude_str, longitude_str)

example_position = {
    "lastGnssFixLon": -2142627826,
    "lastGnssFixLat": -2101724794,
}
# inttt = ugly_decode_jer_geodata_lat_long(-2142627990)
# print(inttt)
# inttt = ugly_decode_jer_geodata_lat_long(-2101724964)
# print(inttt)

print(ugly_decode_jer_absolute_position_2d(example_position))

result = custom_its_per_decoders.decode_jer_dsrc_wgs_84_position({
  "lastGnssFixLon": -2142628748,
  "lastGnssFixLat": -2101724189,
})
print(result)
print(custom_its_per_decoders.decode_jer_dsrc_wgs_84_position({
  "lastGnssFixLon": -2142629736,
  "lastGnssFixLat": -2101725200,
}))