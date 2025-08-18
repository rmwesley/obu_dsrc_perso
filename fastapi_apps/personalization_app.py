from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routers import obu_dsrc_personalization

personalization_app = FastAPI(title='OBU Personalization app')
personalization_app.include_router(prefix='/dsrc', router=obu_dsrc_personalization.router)

personalization_app.mount("/hmi", StaticFiles(directory="fronts/web/perso_app_web_front", html=True), name="perso_app_web_front_files")