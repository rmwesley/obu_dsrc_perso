from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from efc_decoding_app import efc_decoding_app
from efc_security_app import efc_security_app
from beacon_client_app import beacon_client_app
from transaction_data_app import transaction_data_app

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

root_app = FastAPI(title="Main app")

@root_app.get('/', include_in_schema=False)
async def get_index():
    return FileResponse('fronts/tolling_testing_web_front/index.html')

@root_app.get('/home.svg', include_in_schema=False)
async def favicon():
    return FileResponse('fronts/tolling_testing_web_front/home.svg')

# Mount the subapps
root_app.mount("/decoding", efc_decoding_app)
root_app.mount("/security", efc_security_app)
root_app.mount("/beacon", beacon_client_app)
root_app.mount("/transacation-data", transaction_data_app)