from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from routers import tsp_dsrc_security_kapsch_uset

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

tsp_efc_security_app = FastAPI(title="Toll Service Provider EFC Security Tests API")

tsp_efc_security_app.include_router(tsp_dsrc_security_kapsch_uset.router)