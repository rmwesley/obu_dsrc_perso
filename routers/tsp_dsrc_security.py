from fastapi import APIRouter, Request

from pydantic import BaseModel, Field
from typing import Optional

import logging

security_router_logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/security",
    tags=["TSP DSRC Security Interface"])