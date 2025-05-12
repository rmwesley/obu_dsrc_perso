from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from routers import dsrc_transaction_data, beacon

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

root_app = FastAPI(title="Beacon Client API")

@root_app.get('/', include_in_schema=False)
async def get_index():
    return FileResponse('beacon_client_front/static/index.html')

@root_app.get('/home.svg', include_in_schema=False)
async def favicon():
    return FileResponse('beacon_client_front/static/home.svg')

root_app.include_router(dsrc_transaction_data.router)
root_app.include_router(beacon.router)

# Serve the static HTML files for each subapp
root_app.mount("/", StaticFiles(directory="beacon_client_front/static/"), name="static")

root_app.include_router(beacon.router)

# Serve the static HTML files for each subapp
root_app.mount("/", StaticFiles(directory="rse_web_front/static/"), name="static")