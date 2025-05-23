from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# from routers import beacon, security, efc_decoding
from routers import efc_decoding

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

efc_decoding_app = FastAPI(title="EFC Decoding API")

# @efc_decoding_app.get('/', include_in_schema=False)
# async def get_index():
#     return FileResponse('index.html')

# @efc_decoding_app.get('/home.svg', include_in_schema=False)
# async def favicon():
#     return FileResponse('fronts/efc_decoding_front/static/home.svg')

# efc_decoding_app.include_router(beacon.router)
efc_decoding_app.include_router(efc_decoding.router)

# Serve the static HTML files for this app
efc_decoding_app.mount("/", StaticFiles(directory="fronts/efc_decoder_web_front", html=True), name="efc_decoder_web_front_files")