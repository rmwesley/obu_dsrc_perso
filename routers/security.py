from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel, Field
from typing import Optional

import logging
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
@router.get('/security.svg', include_in_schema=False)
async def favicon():
    return FileResponse('static/security_interface/security.svg')

class TripleDesDecryptionReq(BaseModel):
    ciphertext: str
    key: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "ciphertext": "8B1300F0E421D5DB",
                    "key": "A6B57FC2D327F348F6E258428E94DCE0"
                }
            ]
        }
    }

@router.post("/triple_des_decryt")
def triple_des_decryt(req_body: TripleDesDecryptionReq):
    return dsrc_security.triple_des_decryption(req_body.ciphertext, req_body.key)

class TripleDesEncryptionReq(BaseModel):
    plaintext: str
    key: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "plaintext": "35557965b2803100",
                    "key": "A6B57FC2D327F348F6E258428E94DCE0"
                }
            ]
        }
    }

@router.post("/triple_des_encryt")
def triple_des_encryt(req_body: TripleDesEncryptionReq):
    return dsrc_security.triple_des_encryption(req_body.plaintext, req_body.key)

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

class ComputeAllDerivedKeysForAllKeySetsReq(BaseModel):
    pan_id: str = Field(min_length=16, max_length=20)
    ac_cr_key_ref: str = Field(max_length=4)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "pan_id": "3156496003252000650",
                    "ac_cr_key_ref": "0018"
                }
            ]
        }
    }
@router.post("/compute_all_derived_keys_for_all_keysets")
def compute_all_derived_keys_for_all_keysets(req_body: ComputeAllDerivedKeysForAllKeySetsReq):
    ac_cr_key_ref = int(req_body.ac_cr_key_ref, 16)
    return dsrc_security.compute_all_derived_keys_for_available_keysets_and_return_hex_dict(req_body.pan_id, ac_cr_key_ref)

class ComputeAllDerivedKeysForDeviceTypeReq(BaseModel):
    pan_id: str = Field(min_length=16, max_length=20)
    ac_cr_key_ref: str = Field(max_length=4)
    device_type: str = Field(max_length=12)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "pan_id": "3156496003252000650",
                    "ac_cr_key_ref": "0018",
                    "device_type": "C3081"
                }
            ]
        }
    }
@router.post("/compute_all_derived_keys_for_device_type")
def compute_all_derived_keys_for_device_type(req_body: ComputeAllDerivedKeysForDeviceTypeReq):
    ac_cr_key_ref = int(req_body.ac_cr_key_ref, 16)
    return dsrc_security.compute_all_derived_keys_for_device_type_and_return_hex_dict(req_body.pan_id, req_body.device_type, ac_cr_key_ref)

class ComputeAccessKeyReq(BaseModel):
    efc_cm: str = Field(min_length=12, max_length=12, examples=["B28031000665", "B2803100066F", "B28031000A72"])
    ac_cr_key_ref: str = Field(max_length=4)

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

class ComputeAllDerivedKeysReq(BaseModel):
    efc_cm: str
    pan_id: str = Field(min_length=16, max_length=20)
    ac_cr_key_ref: str = Field(max_length=4)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "efc_cm": "B2803100066F",
                    "pan_id": "3156496003252000650",
                    "ac_cr_key_ref": "0018"
                }
            ]
        }
    }
@router.post("/compute_all_derived_keys")
def compute_key_checksum_values(req_body: ComputeAllDerivedKeysReq):
    ac_cr_key_ref = int(req_body.ac_cr_key_ref, 16)
    return dsrc_security.compute_all_derived_keys_and_return_hex_dict(req_body.pan_id, req_body.efc_cm, ac_cr_key_ref)

@router.post("/compute_all_derived_keys_in_jer_format")
def compute_key_checksum_values(req_body: ComputeAllDerivedKeysReq):
    ac_cr_key_ref = int(req_body.ac_cr_key_ref, 16)
    derived_keys_hex_dict = dsrc_security.compute_all_derived_keys_and_return_hex_dict(req_body.pan_id, req_body.efc_cm, ac_cr_key_ref)
    return [{
        "attributeId": key_ref,
        "attributeValue": {
            "octet_string": "0208" + derived_key_value
        }
    } for key_ref, derived_key_value in derived_keys_hex_dict.items()]

@router.post("/compute_all_derived_keys_in_proxy_format")
def compute_key_checksum_values(req_body: ComputeAllDerivedKeysReq):
    ac_cr_key_ref = int(req_body.ac_cr_key_ref, 16)
    derived_keys_hex_dict = dsrc_security.compute_all_derived_keys_and_return_hex_dict(req_body.pan_id, req_body.efc_cm, ac_cr_key_ref)
    return [{
        "attribute": key_ref,
        "value": "0208" + derived_key_value
    } for key_ref, derived_key_value in derived_keys_hex_dict.items()]

class ComputeAuthKeyReq(BaseModel):
    efc_cm: str
    pan_id: str
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
    efc_cm: str
    auth_key: str
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
    access_key = dsrc_security.compute_access_key(efc_cm, ac_cr_key_ref).hex().upper()

    return access_key

@router.post("/compute_auth_keys")
def compute_auth_keys(req_body: ComputeAuthKeyReq) -> dict[int, str]:
    pan_id = req_body.pan_id
    efc_cm = req_body.efc_cm
    key_ref = req_body.key_ref

    if not key_ref:
        return dsrc_security.compute_all_auth_keys_and_return_hex_dict(pan_id, efc_cm)
    if key_ref < 111:
        key_ref += 110

    auth_key = dsrc_security.compute_auth_key_with_mauk_ref(pan_id, efc_cm, key_ref).hex().upper()
    return {key_ref: auth_key}


@router.post("/security/decipher_auth_key")
def deciphAuthKey(req_body: AuthKeyDeciphReq):
    auth_key = req_body.auth_key
    efc_cm = req_body.efc_cm
    key_ref = req_body.key_ref

    deciphered_ciphertext = dsrc_security.decipher_auth_key_with_mauk_ref(auth_key, efc_cm, key_ref).hex().upper()
    return deciphered_ciphertext