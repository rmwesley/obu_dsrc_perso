from fastapi import APIRouter, Request

from pydantic import BaseModel, Field
from typing import Optional

from dsrc_security import perso_security_operations

import logging

security_router_logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/security",
    tags=["TSP DSRC Security Interface"])

class UsetDerivedKeyDecryptionReq(BaseModel):
    obu_model: str
    uset_derived_key_hex: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "obu_model": "TRP-4010-20B",
                    "uset_derived_key_hex": "E6F6740DC43FDA716C1FF0A25FC7E47F"
                },
                {
                    "obu_model": "TRP-4010-20B",
                    "uset_derived_key_hex": "52CF61BFF3369741EC2E34EA8103AD5F"
                },
            ]
        }
    }

@router.post("/decrypt_uset_key")
def triple_des_decryt(req_body: UsetDerivedKeyDecryptionReq):
    ciphertext = bytes.fromhex(req_body.uset_derived_key_hex)
    plaintext_bytes = perso_security_operations.decrypt_uset_derived_key_for_obu_model(
        obu_model=req_body.obu_model,
        ciphertext=ciphertext,
        uset_key_type=req_body.uset_key_type)
    return plaintext_bytes.hex().upper()