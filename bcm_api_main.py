from fastapi import FastAPI
from fastapi.responses import FileResponse

from routers import beacon, security

import logging
logging.basicConfig(
    format=f"%(levelname)-8s %(filename)22s:%(lineno)s - %(funcName)s() - %(threadName)s %(message)s",
    level=logging.DEBUG
    )

root_app = FastAPI(title="TSP Testing API")

@root_app.get('/', include_in_schema=False)
async def get_index():
    return FileResponse('static/index.html')

@root_app.get('/home.svg', include_in_schema=False)
async def favicon():
    return FileResponse('static/home.svg')

root_app.include_router(beacon.router)
root_app.include_router(security.router)

# Serve the static HTML files for each subapp
# root_app.mount("/", StaticFiles(directory="static/", html=True), name="static")
# beacon_manager_app.mount("/beacon_management", StaticFiles(directory="static/beacon_management/", html=True), name="Beacon Manager")
