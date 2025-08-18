from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from fastapi_apps.efc_decoding_app import efc_decoding_app
from fastapi_apps.efc_security_app import efc_security_app
from fastapi_apps.beacon_client_app import beacon_client_app
from fastapi_apps.dsrc_transaction_data_app import transaction_data_app
from fastapi_apps.toll_domain_zones_app import td_zones_app
from fastapi_apps.rse_gps_sync_app import rse_gps_td_app
from fastapi_apps.personalization_app import personalization_app

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

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
root_logger.addHandler(file_handler)


app = FastAPI(title="Main FastAPI app")

@app.get('/', include_in_schema=False)
async def redirect_index_to_hmi():
    return RedirectResponse('/hmi')

# Mount the webapp (frontend static files)
app.mount("/hmi", StaticFiles(directory="fronts/web/tolling_testing_web_front", html=True), name="tolling_testing_web_front_files")

# Mount the subapps
app.mount("/decoding", efc_decoding_app)
app.mount("/security", efc_security_app)
app.mount("/beacon", beacon_client_app)
app.mount("/dsrc-transactions/", transaction_data_app)
app.mount("/td_zones", td_zones_app)
app.mount("/rse_gps", rse_gps_td_app)
app.mount("/perso_app", personalization_app)