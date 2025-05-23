from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# from routers import beacon, security, efc_decoding
from routers import security

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

efc_security_app = FastAPI(title="EFC Testing API")

# @efc_sec_app.get('/', include_in_schema=False)
# async def get_index():
#     return FileResponse('index.html')

# @efc_sec_app.get('/home.svg', include_in_schema=False)
# async def favicon():
#     return FileResponse('fronts/efc_decoding_front/static/home.svg')

# efc_sec_app.include_router(beacon.router)
efc_security_app.include_router(security.router)

# Serve the static HTML files for this app
efc_security_app.mount("/", StaticFiles(directory="fronts/security_interface_web_front", html=True), name="sec_if_static_files")
