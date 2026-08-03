from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from fastapi_apps.beacon_client_app import beacon_client_app
from fastapi_apps.dsrc_transaction_data_app import transaction_data_app
from fastapi_apps.toll_domain_zones_app import td_zones_app
from fastapi_apps.rse_gps_sync_app import rse_gps_td_app

from contextlib import asynccontextmanager, AsyncExitStack
from fastapi_apps.personalization_app import personalization_app
from fastapi_apps.dsrc_interop_app import dsrc_interop_app

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(
            personalization_app.router.lifespan_context(personalization_app)
        )
        yield

import logging
root_logger = logging.getLogger()

for name in root_logger.manager.loggerDict.keys():
    if "watchfiles.main" in name:
        # print(name)
        logging.getLogger(name).disabled = True
        logging.getLogger(name).propagate = False
        pass

from datetime import datetime
log_file_date_prefix = datetime.now().strftime('%Y%m%d')
# SETTING UP LOGGER FILE HANDLER
file_handler = logging.FileHandler(f'logs/api_logs/{log_file_date_prefix}_api_logs.log')
file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
# file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)
file_handler.setLevel(logging.INFO)
root_logger.addHandler(file_handler)


app = FastAPI(title="Main FastAPI app", lifespan=lifespan)

@app.get('/', include_in_schema=False)
async def redirect_index_to_hmi():
    return RedirectResponse('/hmi')

# Mount the webapp (frontend static files)
app.mount("/hmi", StaticFiles(directory="fronts/web/tolling_testing_web_front", html=True), name="tolling_testing_web_front_files")

# Mount the subapps
app.mount("/beacon", beacon_client_app)
app.mount("/dsrc-transactions/", transaction_data_app)
app.mount("/td_zones", td_zones_app)
app.mount("/rse_gps", rse_gps_td_app)
app.mount("/perso_app", personalization_app)
app.mount("/dsrc-interop", dsrc_interop_app)
app.mount("/asn-compiler", StaticFiles(directory="fronts/web/asn_compiler_web_front", html=True), name="asn_compiler_web_front_files")