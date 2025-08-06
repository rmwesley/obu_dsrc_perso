from fastapi import FastAPI

from routers import obu_personalization

personalization_app = FastAPI(title='OBU Personalization app')
personalization_app.include_router(prefix='/data', router=obu_personalization.router)