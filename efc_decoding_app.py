from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routers import efc_decoding

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

efc_decoding_app = FastAPI(title="EFC Decoding API")

efc_decoding_app.include_router(efc_decoding.router)

# Serve the static HTML files for this app
efc_decoding_app.mount("/", StaticFiles(directory="fronts/web/efc_decoder_web_front", html=True), name="efc_decoder_web_front_files")