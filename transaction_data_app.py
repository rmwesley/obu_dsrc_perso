from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routers import dsrc_transaction_data

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

transaction_data_app = FastAPI(title="Transaction Data API")
transaction_data_app.include_router(dsrc_transaction_data.router)