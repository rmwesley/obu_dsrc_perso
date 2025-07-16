from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from routers import dsrc_transaction_data

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

transaction_data_app = FastAPI(title="Transaction Data API")
transaction_data_app.include_router(dsrc_transaction_data.router)

@transaction_data_app.get('/', include_in_schema=False)
async def redirect_index_to_hmi():
    return RedirectResponse('/dsrc-transactions/hmi')

# Serve the static HTML files for this app
transaction_data_app.mount(
    "/hmi",
    StaticFiles(directory="fronts/web/transaction_data_web_front/", html=True),
    name="transaction_data_web_front_files"
)