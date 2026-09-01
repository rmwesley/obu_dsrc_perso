import asyncio
from datetime import datetime
import logging

from ..globals import LOG_DIR, SETTINGS_DIR
from ..bac_l7 import ops1955_bac_l7, pertel_bac_l7, tgbv_bac_l7

# File logger, so prevent propagation!!
bcm_logger = logging.getLogger(__name__)
bcm_logger.setLevel(logging.DEBUG)
bcm_logger.propagate = False

startup_date = datetime.now()
logs_date_prefix = startup_date.strftime('%y%m%d')

# SETTING UP LOGGER FILE HANDLER
bcm_logs_path = LOG_DIR / f'beacon_logs/{logs_date_prefix}_bcm.log'
bcm_logs_path.parent.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(bcm_logs_path)
file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)
bcm_logger.addHandler(file_handler)

# Setting globals
## Garbage unsafe temporary globals
keep_looping = False

## SKIP DSRC AUTH
SKIP_CONTRACT_DSRC_AUTH = False

RSE_DRIVERS_DIR = SETTINGS_DIR / "rse_drivers"
if not RSE_DRIVERS_DIR.exists() or not RSE_DRIVERS_DIR.glob("*.json"):
    raise FileNotFoundError("Please keep at least one RSE driver JSON config file in settings/rse_drivers/!")

def conf_exists(beacon_name:str):
    bcm_conf_filepath = RSE_DRIVERS_DIR / f"{beacon_name}.json"

    return bcm_conf_filepath.exists()

def find_first_conf_name():
    filepath = next(RSE_DRIVERS_DIR.glob("*.json"))
    beacon_name = filepath.stem
    return beacon_name

def load_beacon_name_from_file():
    with ( SETTINGS_DIR / "beacon_name.txt" ).open('r') as txf_file:
        beacon_name = txf_file.read()
    return beacon_name

def get_default_beacon_name():
    beacon_name = load_beacon_name_from_file()

    if conf_exists(beacon_name):
        return beacon_name
    else:
        bcm_logger.warning(f"Undefined beacon name in '{beacon_name}': {beacon_name}")
        # Workaround: try getting the first conf file in rse_drivers/ dir...
        default_beacon_name = find_first_conf_name()

        bcm_logger.warning(f"Using beacon name {default_beacon_name} instead...")
        return default_beacon_name

async def get_bac_l7_driver(beacon_name:str):
    """Get the beacon driver for beacon_name"""
    if beacon_name == 'TGBV':
        beacon_driver = tgbv_bac_l7.TgbvBacL7()
        return beacon_driver

    if beacon_name == 'OPS1955':
        beacon_driver = ops1955_bac_l7.Ops1955BacL7()
        await beacon_driver.kapsch_set_config_from_settings()

        return beacon_driver
    raise ValueError(f"Driver for beacon_name {beacon_name} not implemented!")

async def close_and_update_beacon_driver(
        current_driver:pertel_bac_l7.PertelBacL7|None,
        beacon_name:str,
    ):
    """Close the current beacon, and get the new beacon driver from its name"""
    bcm_logger.info(f'Setting beacon to ({beacon_name})')

    if current_driver is not None:
        current_driver.close()

    return get_bac_l7_driver(beacon_name)

class BacDriverManager():
    def __init__(self, beacon_name:str) -> None:
        self.beacon_name:str|None   = beacon_name
        self.bcm_config:dict|None   = None
        self.rse_bac_l7_driver      = asyncio.run(get_bac_l7_driver(beacon_name))

    async def safe_set_beacon_driver(self, beacon_name:str):
        """Safely set the beacon driver (close previous driver beforehand if set)"""
        await close_and_update_beacon_driver(self.rse_bac_l7_driver, beacon_name)

    async def force_config_default_driver(self):
        beacon_name = get_default_beacon_name()

        await self.safe_set_beacon_driver(beacon_name)

# Host PC <> RSE:
# Host <> Host BAC L7 <> Host BAC L2 <RS232> Beacon BAC L2 <> Beacon RSE
def bac_l7_driver(beacon_name: str):
    driver_manager = BacDriverManager(beacon_name)
    return driver_manager

async def bac_l7_force_default_driver():
    beacon_name = get_default_beacon_name()
    driver_manager = BacDriverManager(beacon_name)
    await driver_manager.force_config_default_driver()
    return driver_manager
