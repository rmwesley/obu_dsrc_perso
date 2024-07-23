from fastapi import FastAPI
from pydantic import BaseModel, Field

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

@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/transparent")
async def set_transparent():
    router_logger.debug("Changed mode to transparent!")
    app.state.beacon_manager.change_mode(1)
@app.get("/initialization")
async def get_rq():

    router_logger.debug("Initializing!")
    vst_obj = app.state.beacon_manager.initialization()
    return {"VST" : vst_obj}