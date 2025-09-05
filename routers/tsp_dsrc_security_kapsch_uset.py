from fastapi import APIRouter, Request

from pydantic import BaseModel, Field
from typing import Optional

from dsrc_security import perso_security_operations

import logging

security_router_logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/kapsch-sec",
    tags=["TSP DSRC Security Interface"])

class ComputeUsetDerivedKeyReq(BaseModel):
    obu_model: str
    ac_cr_key_ref_hex: str
    uset_key_type: perso_security_operations.TRP_4010_20B_MK_TYPES | None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "obu_model": "TRP_4010_20B_PL",
                    "ac_cr_key_ref_hex": "008E",
                    "uset_key_type": 'Stock'
                },
                {
                    "obu_model": "TRP_4010_20B_PL",
                    "ac_cr_key_ref_hex": "00FA"
                },
                {
                    "obu_model": "TRP_4010_20B_PL",
                    "ac_cr_key_ref_hex": "00FA",
                    "uset_key_type": 'Exploit'
                },
            ]
        }
    }

@router.post("/compute_uset_key")
def compute_uset_key(req_body: ComputeUsetDerivedKeyReq):
    ac_cr_key_ref = int(req_body.ac_cr_key_ref_hex, base=16)
    plaintext_bytes = perso_security_operations.compute_uset_derived_key_for_obu_model(
        obu_model=req_body.obu_model,
        ac_cr_key_ref=ac_cr_key_ref,
        uset_key_type=req_body.uset_key_type)
    return plaintext_bytes.hex().upper()

class UsetDerivedKeyDecryptionReq(BaseModel):
    obu_model: str
    uset_derived_key_hex: str
    uset_key_type: perso_security_operations.TRP_4010_20B_MK_TYPES | None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "obu_model": "TRP_4010_20B_PL",
                    "uset_derived_key_hex": "E6F6740DC43FDA716C1FF0A25FC7E47F",
                    "uset_key_type": 'Stock'
                },
                {
                    "obu_model": "TRP_4010_20B_PL",
                    "uset_derived_key_hex": "52CF61BFF3369741EC2E34EA8103AD5F"
                },
                {
                    "obu_model": "TRP_4010_20B_PL",
                    "uset_derived_key_hex": "C68090FF17CC0B5FC68090FF17CC0B5F",
                    "uset_key_type": 'Exploit'
                },
            ]
        }
    }

@router.post("/decrypt_uset_key")
def decrypt_uset_key(req_body: UsetDerivedKeyDecryptionReq):
    ciphertext = bytes.fromhex(req_body.uset_derived_key_hex)
    plaintext_bytes = perso_security_operations.decrypt_uset_derived_key_for_obu_model(
        obu_model=req_body.obu_model,
        ciphertext=ciphertext,
        uset_key_type=req_body.uset_key_type)
    return plaintext_bytes.hex().upper()

class ComputeUsetAcCr(BaseModel):
    obu_model: str
    ac_cr_key_ref_hex: str
    rnd_obe_hex: str
    uset_key_type: perso_security_operations.TRP_4010_20B_MK_TYPES | None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "obu_model": "TRP_4010_20B_PL",
                    "ac_cr_key_ref_hex": "0053",
                    "rnd_obe_hex": "257B EF72",
                    "uset_key_type": "Exploit"
                },
                {
                    "obu_model": "TRP_4010_20B_PL",
                    "ac_cr_key_ref_hex": "0053",
                    "rnd_obe_hex": "3F9D A89C",
                    "uset_key_type": "Stock"
                }
            ]
        }
    }

@router.post("/compute_uset_ac_cr")
def compute_uset_ac_cr(req_body: ComputeUsetAcCr):
    ac_cr_key_ref = int.from_bytes(bytes.fromhex(req_body.ac_cr_key_ref_hex))
    rnd_obe = int.from_bytes(bytes.fromhex(req_body.rnd_obe_hex))
    plaintext_bytes = perso_security_operations.compute_kapsch_uset_access_credentials_for_obu_model(
        obu_model=req_body.obu_model,
        ac_cr_key_ref=ac_cr_key_ref,
        rnd_obe=rnd_obe,
        uset_key_type=req_body.uset_key_type)
    return plaintext_bytes.hex().upper()