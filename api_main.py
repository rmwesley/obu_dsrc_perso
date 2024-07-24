from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from fastapi.staticfiles import StaticFiles

from contextlib import asynccontextmanager
from beacon_manager import BeaconManager
import logging

router_logger = logging.getLogger()

console_handler = logging.StreamHandler()

class ColoredFormatterWrapper(logging.Formatter):
    GRAY = "\033[38m"
    YELLOW = "\033[33m"
    RED = "\033[31;20m"
    BOLD_RED = "\033[31m"
    BLUE = "\33[34m"
    RESET_COLOR = "\033[0m"
    default_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)")
    formatter = None

    LEVEL_COLORS = {
        logging.DEBUG: GRAY,
        logging.INFO: BLUE,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def __init__(self, formatter=default_formatter):
        self.formatter = formatter

    def format(self, record):
        color = ColoredFormatterWrapper.LEVEL_COLORS.get(record.levelno)
        colored_formatting = color + self.formatter.format(record) + ColoredFormatterWrapper.RESET_COLOR
        return colored_formatting
        
console_formatter = ColoredFormatterWrapper(logging.Formatter(f"%(levelname)-8s %(filename)22s:%(lineno)s - %(funcName)s() - %(threadName)s %(message)s"))
console_handler.setFormatter(console_formatter)

router_logger.addHandler(console_handler)
router_logger.setLevel(logging.DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ''' Run at startup
        Initialise the BeaconManager and add it to app.state
    '''
    app.state.beacon_manager = BeaconManager()
    yield
    ''' Run on shutdown
        Close the connection
        Clear variables and release the resources
    '''
    app.state.beacon_manager.close()

app = FastAPI(lifespan=lifespan)

class GET_rq(BaseModel):
    attribute_id_list: list = Field(default=0x20, description='List of attribute ids to get')

@app.post("/initialization")
async def get_rq():
    router_logger.debug("Initializing!")
    vst_obj = app.state.beacon_manager.initialization()
    return {"VST" : vst_obj}

# Endpoint to get the current beacon state
@app.get("/beacon-state")
async def get_beacon_state():
    app.state.beacon_manager.update_state()
    return {"state": app.state.beacon_manager.bcm_state}

class ChangeModeRequest(BaseModel):
    mode: int
# Endpoint to change the beacon mode
@app.post("/change-mode")
async def change_mode(request: ChangeModeRequest):
    mode = request.mode
    app.state.beacon_manager.change_mode(mode)
    return {"message": f"Changed mode to {mode}"}

# Endpoint to initialize the beacon to access EFC functions
@app.post("/initialize-transaction")
async def initialize():
    vst_obj = app.state.beacon_manager.initialization()
    app.state.beacon_manager.close()
    return {"VST": vst_obj}

# Endpoint to close transaction
@app.post("/close-transaction")
async def close_transaction():
    app.state.beacon_manager.set_mmi(True)
    return {"message": "Transaction closed"}

# Endpoint to initialize the beacon and close transaction
@app.post("/initialize-close-transaction")
async def initialize_close():
    vst_obj = app.state.beacon_manager.initialization()
    app.state.beacon_manager.set_mmi(True)
    return {"VST": vst_obj}

class EFCFunctionRequest(BaseModel):
    function_type: str
    eid: int
    attribute_id_list: list = Field(default_factory=list)
    action_type: str = None

@app.get("/last-vst")
async def get_last_vst():
    last_vst = app.state.beacon_manager.last_vst
    return {"last_vst": last_vst}

# Endpoint to handle EFC functions
@app.post("/efc-function")
async def efc_function(request: EFCFunctionRequest):
    function_type = request.function_type
    eid = request.eid
    attribute_id_list = request.attribute_id_list

    if function_type == "GET":
        response = app.state.beacon_manager.send_get_request(eid, attribute_id_list)
    elif function_type == "SET":
        response = app.state.beacon_manager.send_set_request(eid, attribute_id_list)
    elif function_type == "ACTION":
        action_type = request.action_type
        response = app.state.beacon_manager.send_action_request(eid, action_type, attribute_id_list)
    else:
        raise HTTPException(status_code=400, detail="Invalid function type")
    
    return {"response": response}

# Serve the index.html at the root
app.mount("/", StaticFiles(directory="static", html=True), name="static")