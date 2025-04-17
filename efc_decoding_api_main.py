from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# from routers import beacon, security, efc_decoding
from routers import security, efc_decoding

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

root_app = FastAPI(title="EFC Testing API")

@root_app.get('/', include_in_schema=False)
async def get_index():
    return FileResponse('efc_decoding_front/static/index.html')

@root_app.get('/home.svg', include_in_schema=False)
async def favicon():
    return FileResponse('efc_decoding_front/static/home.svg')

# root_app.include_router(beacon.router)
root_app.include_router(security.router)
root_app.include_router(efc_decoding.router)

# Serve the static HTML files for each subapp
root_app.mount("/", StaticFiles(directory="efc_decoding_front/static/"), name="static")