from fastapi import APIRouter, HTTPException, Request

import datetime
from pydantic import BaseModel, Field

from typing import Literal, Optional
from enum import IntEnum

from services.db import transactions_data_db_operations

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

@router.get('/transaction-data/{equOBUId}')
async def get_transaction_data_for_obu_id(equOBUId:str, skip:str=0, limit:str=10):
    """
    Query transactions database for data related to a specific OBU ID.
    The OBU ID must be in hexadecimal format.
    """
    equOBUId = equOBUId.lower()

    return transactions_data_db_operations.get_transactions_data_for_equ_obu_id(equOBUId)

@router.post('/sync-local-files-to-remote-db')
async def sync_local_data_to_remote_db(request: SyncTransactionDataReq):
    upload_result = transactions_data_db_operations.upload_local_data_since_date(request.start_date)
    return upload_result