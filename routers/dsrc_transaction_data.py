from fastapi import APIRouter, HTTPException, Request

import datetime
from pydantic import BaseModel, Field

from typing import Literal, Optional
from enum import IntEnum

from services.db import transactions_data_sync

router = APIRouter(
    prefix="/transactions-data",
    tags=["DSRC Transaction Data Management Interface"])

class SyncTransactionDataReq(BaseModel):
    start_date: datetime.datetime

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "start_date": "2025-05-06T14:00:00"
                }
            ]
        }
    }
@router.post('/sync-local-files-to-remote-db')
async def sync_local_data_to_remote_db(request: SyncTransactionDataReq):
    upload_result = transactions_data_sync.upload_local_data_since_date(request.start_date)
    return upload_result