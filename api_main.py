from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles

from routers import beacon, security

import logging
logging.basicConfig(
    format=f"%(levelname)-8s %(filename)22s:%(lineno)s - %(funcName)s() - %(threadName)s %(message)s",
    level=logging.DEBUG
    )


root_app = FastAPI(title="TSP Testing API")
security_management_app = APIRouter()


root_app.include_router(beacon.router)
root_app.include_router(security.router)

# Serve the static HTML files for each subapp
root_app.mount("/", StaticFiles(directory="static/", html=True), name="static")
# beacon_manager_app.mount("/beacon_management", StaticFiles(directory="static/beacon_management/", html=True), name="Beacon Manager")
# security_management_app.mount("/security_management", StaticFiles(directory="static/security_management/", html=True), name="Security Management")

