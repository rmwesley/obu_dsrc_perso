from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routers import obu_personalization

personalization_app = FastAPI(title='OBU Personalization app')
personalization_app.include_router(router=obu_personalization.router)

personalization_app.mount("/hmi", StaticFiles(directory="fronts/web/perso_app_web_front", html=True), name="perso_app_web_front_files")