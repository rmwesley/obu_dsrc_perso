from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..routers import beacon

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

root_app = FastAPI(title="RSE API")

@root_app.get('/', include_in_schema=False)
async def get_index():
    return FileResponse('rse_web_front/static/index.html')

@root_app.get('/home.svg', include_in_schema=False)
async def favicon():
    return FileResponse('rse_web_front/static/home.svg')

root_app.include_router(beacon.router)

# Serve the static HTML files for each subapp
root_app.mount("/", StaticFiles(directory="rse_web_front/static/"), name="static")