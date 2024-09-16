from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel, Field

from fastapi.staticfiles import StaticFiles

from contextlib import asynccontextmanager
from beacon_manager import BeaconManager

import logging
logging.basicConfig(
    format=f"%(levelname)-8s %(filename)22s:%(lineno)s - %(funcName)s() - %(threadName)s %(message)s",
    level=logging.DEBUG
    )

# Instantiating BeaconManager as a global attribute
# of the FastAPI application
@asynccontextmanager
async def beacon_manager_lifespan(beacon_manager_app: FastAPI):
    ''' Run at startup
        Initialise the BeaconManager and add it to app.state
    '''
    beacon_manager_app.state.beacon_manager = BeaconManager()
    yield
    ''' Run on shutdown
        Close the connection
        Clear variables and release the resources
    '''
    beacon_manager_app.state.beacon_manager.close()

app = FastAPI(title="TSP Testing API")
beacon_manager_app = FastAPI(title="Beacon Manager API", lifespan=beacon_manager_lifespan)
security_management_app = FastAPI(title="Security API")

# Endpoint to get the current beacon state
@beacon_manager_app.get("/beacon-state")
async def get_beacon_state():
    return {"beacon_state": beacon_manager_app.state.beacon_manager.get_last_beacon_state()}
# Endpoint to update the current beacon state
@beacon_manager_app.post("/update-beacon-state")
async def update_beacon_state():
    beacon_manager_app.state.beacon_manager.update_state()
    return {"beacon_state": beacon_manager_app.state.beacon_manager.get_last_beacon_state()}

class ChangeModeRequest(BaseModel):
    mode: int
# Endpoint to change the beacon mode
@beacon_manager_app.post("/change-mode")
async def change_mode(request: ChangeModeRequest):
    mode = request.mode
    beacon_manager_app.state.beacon_manager.change_mode(mode)
    return {"message": f"Changed mode to {mode}"}

# Endpoint to initialize the beacon to access EFC functions
@beacon_manager_app.post("/initialize-transaction")
async def initialize():
    last_decoded_vst_obj = beacon_manager_app.state.beacon_manager.initialization()
    return {"last_vst": last_decoded_vst_obj}

# Endpoint to close transaction
@beacon_manager_app.post("/send-close-transaction-to-obu")
async def send_close_transaction_to_obu():
    command_response = beacon_manager_app.state.beacon_manager.send_close_transaction_to_obu()
    return {
        "message": "Transaction closed",
        "command_response": command_response
        }

# Endpoint to initialize the beacon and close transaction
@beacon_manager_app.post("/initialize-close-transaction")
async def initialize_close():
    last_decoded_vst_obj = beacon_manager_app.state.beacon_manager.initialization()
    beacon_manager_app.state.beacon_manager.send_close_transaction_to_obu()
    return {"VST": last_decoded_vst_obj}

@beacon_manager_app.get("/last-vst")
async def get_last_vst():
    last_decoded_vst = beacon_manager_app.state.beacon_manager.last_vst_obj
    return {"last_vst": last_decoded_vst}


class GET_rq(BaseModel):
    attribute_id_list: list = Field(default=0x20, description='List of attribute ids to get')

@beacon_manager_app.post("/get-stamped")
async def get_rq():
    command_respose = beacon_manager_app.state.beacon_manager.send_get_stamped_request()
    return {"command_respose" : command_respose}

class EFCFunctionRequest(BaseModel):
    function_type: str
    eid: int
    attribute_id_list: list = Field(default_factory=list)
    action_type: str = None

# Endpoint to handle EFC functions
@beacon_manager_app.post("/efc-function")
async def efc_function(request: EFCFunctionRequest):
    function_type = request.function_type
    eid = request.eid
    attribute_id_list = request.attribute_id_list

    if function_type == "GET":
        response = beacon_manager_app.state.beacon_manager.send_get_request(eid, attribute_id_list)
    elif function_type == "SET":
        response = beacon_manager_app.state.beacon_manager.send_set_request(eid, attribute_id_list)
    elif function_type == "ACTION":
        action_type = request.action_type
        response = beacon_manager_app.state.beacon_manager.send_action_request(eid, action_type, attribute_id_list)
    else:
        raise HTTPException(status_code=400, detail="Invalid function type")
    
    return {"response": response}

app.mount("/beacon", beacon_manager_app)
app.mount("/security", beacon_manager_app)

# Serve the static HTML files for each subapp
app.mount("/", StaticFiles(directory="static/", html=True), name="home")
# beacon_manager_app.mount("/beacon_management", StaticFiles(directory="static/beacon_management/", html=True), name="Beacon Manager")
# security_management_app.mount("/security_management", StaticFiles(directory="static/security_management/", html=True), name="Security Management")

