from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# from routers import dsrc_transaction_data, beacon
from routers import beacon

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

beacon_client_app = FastAPI(title="Beacon Client API")

beacon_client_app.include_router(beacon.router)

# Serve the static HTML files for this app
beacon_client_app.mount("/", StaticFiles(directory="fronts/web/rse_web_front", html=True), name="rse_web_front_files")