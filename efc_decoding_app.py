from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from routers import efc_decoding

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

efc_decoding_app = FastAPI(title="EFC Decoding API")

@efc_decoding_app.get('/', include_in_schema=False)
async def redirect_index_to_hmi():
    return RedirectResponse('/decoding/hmi')

efc_decoding_app.include_router(efc_decoding.router)

# Serve the static HTML files for this app
efc_decoding_app.mount("/hmi", StaticFiles(directory="fronts/web/efc_decoder_web_front", html=True), name="efc_decoder_web_front_files")