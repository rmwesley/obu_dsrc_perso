from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from routers import beacon, security, efc_decoding

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

root_app = FastAPI(title="EFC Testing API")

@root_app.get('/', include_in_schema=False)
async def get_index():
    return FileResponse('static/index.html')

@root_app.get('/home.svg', include_in_schema=False)
async def favicon():
    return FileResponse('static/home.svg')

root_app.include_router(beacon.router)
root_app.include_router(security.router)
root_app.include_router(efc_decoding.router)

# Serve the static HTML files for each subapp
root_app.mount("/", StaticFiles(directory="static/"), name="static")
# beacon_manager_app.mount("/beacon_management", StaticFiles(directory="static/beacon_management/", html=True), name="Beacon Manager")
