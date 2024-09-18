from fastapi import APIRouter, Request

from fastapi.templating import Jinja2Templates
import logging

from pydantic import BaseModel, constr
from typing import Optional

import dsrc_security


templates = Jinja2Templates(directory="templates")
security_router_logger = logging.getLogger(__name__)
# urlpatterns = [
#     path("", router.urls, name="uat-automation"),
#     path("admin/", admin.site.urls, name="admin"),
# ]

router = APIRouter(
    prefix="/security",
    tags=["Security Interface"])

@router.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request,
        name="security_interface.html")

class ComputeKCVsReq(BaseModel):
    efc_cm: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "efc_cm": "B2803100066F"
                }
            ]
        }
    }
@router.post("/compute_kcvs")
def compute_key_checksum_values(req_body: ComputeKCVsReq):
    return dsrc_security.compute_kcvs_for_efc_cm_keyset(req_body.efc_cm)

class ComputeAccessKeyReq(BaseModel):
    efc_cm: str
    ac_cr_key_ref: constr(max_length=4)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "efc_cm": "B2803100066F",
                    "ac_cr_key_ref": "0018"
                }
            ]
        }
    }

class ComputeAuthKeyReq(BaseModel):
    pan_id: str
    efc_cm: str
    key_ref: Optional[int] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "efc_cm": "B2803100066F",
                    "pan_id": "3156496003252000650",
                    "key_ref": 111
                }
            ]
        }
    }

class AuthKeyDeciphReq(BaseModel):
    auth_key: str
    efc_cm: str
    key_ref: Optional[int]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "efc_cm": "B2803100066F",
                    "auth_key": "5533F4A7E5D0EDC0",
                    "key_ref": 111
                }
            ]
        }
    }

@router.post("/compute_access_key")
def compute_access_key(req_body: ComputeAccessKeyReq) -> str:
    efc_cm = req_body.efc_cm
    ac_cr_key_ref = int(req_body.ac_cr_key_ref, 16)
    generated_key = dsrc_security.compute_access_key(efc_cm, ac_cr_key_ref).hex().upper()

    return generated_key

@router.post("/compute_auth_keys")
def compute_auth_keys(req_body: ComputeAuthKeyReq) -> dict[int, str]:
    pan_id = req_body.pan_id
    efc_cm = req_body.efc_cm
    key_ref = req_body.key_ref

    if not key_ref:
        return dsrc_security.compute_all_auth_keys_and_return_hex(pan_id, efc_cm)
    if key_ref < 111:
        key_ref += 110

    generated_key = dsrc_security.compute_auth_key_with_mauk_ref(pan_id, efc_cm, key_ref).hex().upper()
    return {key_ref: generated_key}


@router.post("/security/decipher_auth_key")
def deciphAuthKey(req_body: AuthKeyDeciphReq):
    auth_key = req_body.auth_key
    efc_cm = req_body.efc_cm
    key_ref = req_body.key_ref

    deciphered_ciphertext = dsrc_security.decipher_auth_key_with_mauk_ref(auth_key, efc_cm, key_ref).hex().upper()
    return deciphered_ciphertext