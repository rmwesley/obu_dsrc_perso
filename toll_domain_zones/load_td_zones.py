import json
import pathlib

import shapefile

with pathlib.Path("settings/toll_domain_config.json").open('r') as json_file:
    toll_domain_config = json.load(json_file)
    shapefiles_filename_stem = toll_domain_config['td_zones_gis']['shapefiles_filename_stem']
    td_zones_shp_path = pathlib.Path(shapefiles_filename_stem)

def convert_shapefiles_to_geojson(shapefile_reader):
    geo_json_feature_list = []
    for shape_record in shapefile_reader.shapeRecords():
        geo_json_geometry = shape_record.shape.__geo_interface__
        properties = shape_record.record.as_dict()

        geo_json_feature = {
            "type": "Feature",
            "geometry": geo_json_geometry,
            "properties": properties,
        }
        geo_json_feature_list.append(geo_json_feature)

    geo_json_data = {
        "type": "FeatureCollection",
        "features": geo_json_feature_list
    }
    return geo_json_data

def read_shapefiles_from_config_and_convert_to_geojson():
    shapefile_reader = shapefile.Reader(td_zones_shp_path)

    return convert_shapefiles_to_geojson(shapefile_reader)

if __name__ == '__main__':
    geo_json_data = read_shapefiles_from_config_and_convert_to_geojson()

    with pathlib.Path("local_file_storage/td_zones_files/td_zones_geojson.json").open("w") as geo_json_file:
        json.dump(geo_json_data, geo_json_file, indent=2)