from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routers import dsrc_transaction_data

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

transaction_data_app = FastAPI(title="Transaction Data API")
transaction_data_app.include_router(dsrc_transaction_data.router)

# Serve the static HTML files for this app
transaction_data_app.mount("/hmi", StaticFiles(directory="fronts/web/transaction_data_web_front", html=True), name="tolling_testing_web_front_files")