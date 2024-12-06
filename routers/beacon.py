from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates

from pydantic import BaseModel, Field

from typing import Literal, Optional
from enum import IntEnum

import beacon_manager_module
import dsrc_security

router = APIRouter(
    prefix="/beacon",
    tags=["Beacon Interface"])

templates = Jinja2Templates(directory="templates")
@router.get('/', include_in_schema=False)
def get_beacon_interface(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="beacon_interface.html")
@router.get('/beacon.svg', include_in_schema=False)
async def favicon():
    return FileResponse('static/beacon_interface/beacon.svg')

# Endpoint to initialize the Beacon Manager
# It instantiates a BeaconManager object and keeps it as a global attribute
# of the FastAPI application
@router.post("/initialize-beacon-manager")
async def initialize_beacon_manager():
    ''' Initialize the BeaconManager
    '''
    beacon_manager_module.initialize_bcm()
    return "Beacon Manager was intialized!"

@router.post("/reset-beacon")
async def shutdown():
    ''' Reset beacon
    '''
    beacon_manager_module.reset_beacon()
    return "Beacon Manager was shut down!"

@router.post("/shutdown-manager")
async def shutdown():
    ''' Run on shutdown
        Close the connection
        Clear variables and release the resources
    '''
    beacon_manager_module.shutdown_beacon()
    return "Beacon Manager was shut down!"

class LoopRequest(BaseModel):
    loop_state: str
@router.post("/loop-transactions")
async def loop_transactions(loop_req: LoopRequest):
    ''' Manage Loop Transactions
    '''
    if loop_req.loop_state == 'ON':
        beacon_manager_module.loop_transactions()
        return "looping transactions!!"
    if loop_req.loop_state == 'OFF':
        beacon_manager_module.stop_loop()
        return "Killed loop!!"

# Endpoint to get the current beacon state
@router.get("/beacon-state")
async def get_beacon_state():
    return {"beacon_state": beacon_manager_module.get_last_beacon_state()}

# Endpoint to update the current beacon state
@router.post("/update-beacon-state")
async def update_beacon_state():
    beacon_manager_module.update_state()
    return {"beacon_state": beacon_manager_module.get_last_beacon_state()}


class ChangeModeRequest(BaseModel):
    mode_name: Literal['Transparent', 'Stopped', 'Maintenance']

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "mode_name": 'Transparent'
                },
                {
                    "mode_name": 'Stopped'
                },
                {
                    "mode_name": 'Maintenance'
                }
            ]
        }
    }
# Endpoint to change the beacon mode
@router.post("/change-mode")
async def change_mode(request_body: ChangeModeRequest):
    mode_name = request_body.mode_name
    beacon_manager_module.change_mode(mode_name=mode_name)
    return {"message": f"Changed mode to {mode_name}!"}

# Endpoint to initialize the beacon to access EFC functions
@router.post("/initialize-transaction")
async def initialize_transaction():
    try:
        last_decoded_vst_obj = beacon_manager_module.initialize_transaction()
    except BeaconManagerException as beacon_error:
        raise HTTPException(status_code=400, detail=f"{type(beacon_error).__name__}: {beacon_error}")
    return {"last_vst": last_decoded_vst_obj}

class GetRequest(BaseModel):
    eid:int
    accessCredentialsPresent: Optional[bool] = True
    attrIdList:list = [32]
    close_transaction: Optional[bool] = False

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "eid": 4,
                    "accessCredentialsPresent": True,
                    "attrIdList": [32],
                    "close_transaction": False
                }
            ]
        }
    }
@router.post("/send_get_request")
async def send_get_request(request_body: GetRequest):
    get_response_json = beacon_manager_module.send_get_request(**request_body.dict())
    return {
        "message": "Transaction closed!",
        "response_t_apdu": get_response_json
        }

class PresentationReq(BaseModel):
    eid:int
    accessCredentialsPresent: Optional[bool] = True
    attrIdList:list = [32]
    operator_auk_ref:int = 111
    close_transaction: Optional[bool] = False

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "eid": 3,
                    "accessCredentialsPresent": True,
                    "attrIdList": [32],
                    "operator_auk_ref": 111,
                    "close_transaction": False
                }
            ]
        }
    }
@router.post("/send_presentation_request")
async def send_presentation_request(request_body: PresentationReq):
    get_stamped_response_json = beacon_manager_module.presentation_request(**request_body.dict())
    return {
        "message": "Transaction closed!",
        "response_t_apdu": get_stamped_response_json
        }

# Endpoints to close transaction
@router.post("/send-close-transaction-echo-to-obu")
async def send_close_transaction_echo_to_obu():
    response_t_apdu_json = beacon_manager_module.send_close_transaction_echo()
    return {
        "message": "Transaction closed!",
        "response_t_apdu": response_t_apdu_json
        }
@router.post("/send-close-transaction-set-mmi-to-obu")
async def send_close_set_mmi_to_obu():
    response_t_apdu_json = beacon_manager_module.send_close_transaction_setmmi()
    return {
        "message": "Transaction closed!",
        "response_t_apdu": response_t_apdu_json
        }

# Endpoint to initialize the beacon and close transaction
@router.post("/initialize-and-close-transaction")
async def initialize_and_close_transaction():
    t_apdu_response_list = []
    beacon_manager_module.initialize_transaction()
    t_apdu_response_list.append(beacon_manager_module.last_response_t_apdu_json)

    beacon_manager_module.send_close_transaction_setmmi()
    t_apdu_response_list.append(beacon_manager_module.last_response_t_apdu_json)
    return t_apdu_response_list

@router.get("/last_response_t_apdu_with_vst_json")
async def get_last_vst():
    return beacon_manager_module.last_response_t_apdu_with_vst_json

@router.get("/last_response_t_apdu_json")
async def get_last_vst():
    return beacon_manager_module.last_response_t_apdu_json

class EFCFunctionRequest(BaseModel):
    function_type: str
    eid: int
    attribute_id_list: list = Field(default_factory=list)
    action_type: str = None

class TransactionReq(BaseModel):
    eid: int = 3

@router.post("/CARDME")
async def cardme(request_body: TransactionReq):
    return beacon_manager_module.cardme_transaction(request_body.eid)

@router.post("/Get_all_128_attrs")
async def get_all_attributes(request_body: TransactionReq):
    return beacon_manager_module.get_all_attributes(request_body.eid)

class EFCFunctionRequest(BaseModel):
    pass
# Endpoint to handle EFC functions
@router.post("/efc-function")
async def efc_function(request: EFCFunctionRequest):
    request_body = (await request.json())
    function_type = request_body.function_type
    eid = request_body.eid
    attribute_id_list = request_body.attribute_id_list

    if function_type == "GET":
        response = beacon_manager_module.send_get_request(eid, attribute_id_list)
    elif function_type == "SET":
        response = beacon_manager_module.send_set_request(eid, attribute_id_list)
    elif function_type == "ACTION":
        action_type = request_body.action_type
        response = beacon_manager_module.send_action_request(eid, action_type, attribute_id_list)
    else:
        raise HTTPException(status_code=400, detail="Invalid function type")
    
    return {"response": response}