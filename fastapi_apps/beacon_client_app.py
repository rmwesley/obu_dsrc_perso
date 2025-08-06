from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from routers import beacon

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

beacon_client_app = FastAPI(title="Beacon Client API")

@beacon_client_app.get('/', include_in_schema=False)
async def redirect_index_to_hmi():
    return RedirectResponse('/beacon/hmi')

beacon_client_app.include_router(beacon.router)

# Serve the static HTML files for this app
beacon_client_app.mount("/hmi", StaticFiles(directory="fronts/web/rse_web_front", html=True), name="rse_web_front_files")