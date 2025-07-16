from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from efc_decoding_app import efc_decoding_app
from efc_security_app import efc_security_app
from beacon_client_app import beacon_client_app
from transaction_data_app import transaction_data_app

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

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
app.mount("/transaction-data", transaction_data_app)