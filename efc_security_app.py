from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from routers import security

import logging
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

efc_security_app = FastAPI(title="EFC Testing API")

@efc_security_app.get('/', include_in_schema=False)
async def redirect_index_to_hmi():
    return RedirectResponse('/security/hmi')

efc_security_app.include_router(security.router)

# Serve the static HTML files for this app
efc_security_app.mount("/hmi", StaticFiles(directory="fronts/web/security_interface_web_front", html=True), name="sec_if_static_files")