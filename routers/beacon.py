from fastapi import APIRouter, HTTPException, Request

from pydantic import BaseModel, Field
from beacon_manager import BeaconManager

router = APIRouter(
    prefix="/beacon",
    tags=["Beacon Interface"])

# Endpoint to initialize the Beacon Manager
# It instantiates a BeaconManager object and keeps it as a global attribute
# of the FastAPI application
@router.post("/initialize-manager")
async def initialize_beacon_manager(request: Request):
    ''' Initialise the BeaconManager and add it to app.state
    '''
    root_app = request.app
    root_app.state.beacon_manager = BeaconManager()
    return "Beacon Manager was intialized!"

@router.post("/shutdown-manager")
async def shutdown(request: Request):
    ''' Run on shutdown
        Close the connection
        Clear variables and release the resources
    '''
    root_app = request.app
    root_app.state.beacon_manager.shutdown()
    return "Beacon Manager was shut down!"

# Endpoint to get the current beacon state
@router.get("/beacon-state")
async def get_beacon_state(request: Request):
    return {"beacon_state": request.app.state.beacon_manager.get_last_beacon_state()}
# Endpoint to update the current beacon state
@router.post("/update-beacon-state")
async def update_beacon_state(request: Request):
    request.app.state.beacon_manager.update_state()
    return {"beacon_state": request.app.state.beacon_manager.get_last_beacon_state()}

class ChangeModeRequest(Request):
    mode: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "mode": 1
                }
            ]
        }
    }
# Endpoint to change the beacon mode
@router.post("/change-mode")
async def change_mode(request: ChangeModeRequest):
    mode = (await request.json())["mode"]
    request.app.state.beacon_manager.change_mode(mode)
    return {"message": f"Changed mode to {mode}!"}

# Endpoint to initialize the beacon to access EFC functions
@router.post("/initialize-transaction")
async def initialize(request: Request):
    last_decoded_vst_obj = request.app.state.beacon_manager.initialization()
    return {"last_vst": last_decoded_vst_obj}

# Endpoint to close transaction
@router.post("/send-close-transaction-to-obu")
async def send_close_transaction_to_obu(request: Request):
    command_response = request.app.state.beacon_manager.send_close_transaction_to_obu()
    return {
        "message": "Transaction closed",
        "command_response": command_response
        }

# Endpoint to initialize the beacon and close transaction
@router.post("/initialize-close-transaction")
async def initialize_close(request: Request):
    last_decoded_vst_obj = request.app.state.beacon_manager.initialization()
    request.app.state.beacon_manager.send_close_transaction_to_obu()
    return {"VST": last_decoded_vst_obj}

@router.get("/last-vst")
async def get_last_vst(request: Request):
    last_decoded_vst = request.app.state.beacon_manager.last_vst_obj
    return {"last_vst": last_decoded_vst}


class GET_rq(BaseModel):
    attribute_id_list: list = Field(default=0x20, description='List of attribute ids to get')

@router.post("/get-stamped")
async def get_rq(request: Request):
    command_respose = request.app.state.beacon_manager.send_get_stamped_request()
    return {"command_respose" : command_respose}

class EFCFunctionRequest(Request):
    function_type: str
    eid: int
    attribute_id_list: list = Field(default_factory=list)
    action_type: str = None

# Endpoint to handle EFC functions
@router.post("/efc-function")
async def efc_function(request: EFCFunctionRequest):
    request_body = (await request.json())
    function_type = request_body.function_type
    eid = request_body.eid
    attribute_id_list = request_body.attribute_id_list

    if function_type == "GET":
        response = request.app.state.beacon_manager.send_get_request(eid, attribute_id_list)
    elif function_type == "SET":
        response = request.app.state.beacon_manager.send_set_request(eid, attribute_id_list)
    elif function_type == "ACTION":
        action_type = request_body.action_type
        response = request.app.state.beacon_manager.send_action_request(eid, action_type, attribute_id_list)
    else:
        raise HTTPException(status_code=400, detail="Invalid function type")
    
    return {"response": response}