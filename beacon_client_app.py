from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# from routers import dsrc_transaction_data, beacon
from routers import beacon

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

beacon_client_app = FastAPI(title="Beacon Client API")

# @beacon_client_app.get('/', include_in_schema=False)
# async def get_index():
#     return FileResponse('fronts/beacon_client_web_front/static/index.html')

# @beacon_client_app.get('/home.svg', include_in_schema=False)
# async def favicon():
#     return FileResponse('fronts/beacon_client_web_front/static/home.svg')

# root_app.include_router(dsrc_transaction_data.router)
beacon_client_app.include_router(beacon.router)

# Serve the static HTML files for this app
beacon_client_app.mount("/", StaticFiles(directory="fronts/rse_web_front", html=True), name="rse_web_front_files")