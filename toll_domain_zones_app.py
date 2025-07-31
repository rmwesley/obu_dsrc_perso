from fastapi import FastAPI, staticfiles

from toll_domain_zones import load_td_zones

td_zones_app = FastAPI(title="Toll Domain Zones Interface")

@td_zones_app.post("/regenerate_td_zones_geojson_file")
async def regenerate_td_zones_geojson_file():
    """Regenerate Toll Domain Zones geoJSON file from stored Shapefiles"""
    load_td_zones.regenerate_td_zones_geojson_file()
    return 'Toll Domain Zones geoJSON file updated!!'

td_zones_app.mount("/files", staticfiles.StaticFiles(directory='local_file_storage/td_zones_files'))