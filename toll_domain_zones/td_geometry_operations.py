import json
import pathlib

import shapefile
import shapely

with pathlib.Path("settings/toll_domain_config.json").open('r') as json_file:
    toll_domain_config = json.load(json_file)
    shapefiles_filename_stem = toll_domain_config['td_zones_gis']['shapefiles_filename_stem']
    td_zones_shp_path = pathlib.Path(shapefiles_filename_stem)

def get_td_name_from_gps_coords(latitude:float, longitude:float):
    gps_point = shapely.Point(longitude, latitude)
    # print(gps_point)

    shapefile_reader = shapefile.Reader(td_zones_shp_path)
    for shape_record in shapefile_reader:
        zone_polygon = shapely.Polygon(shape_record.shape.points)
        if zone_polygon.contains(gps_point):
            print(shape_record.record.as_dict())
            return shape_record.record['TollDomain']

    # Default Toll Domain when no GPS signal is available
    return 'TIS'

if __name__ == '__main__':
    td_name = get_td_name_from_gps_coords(45.7593685, 4.8557787)
    print(td_name)