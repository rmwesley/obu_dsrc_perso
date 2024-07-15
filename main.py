import sys
import threading
import logging
import custom_der_decoders

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from python_dll_loader import *
from BeaconManager import BeaconManager

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: [%(threadName)s] %(message)s ",
    handlers=[
        logging.FileHandler("gea_bcm_dll_python_loader.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)



def main():
    logger.debug("Instantiating BeaconManager class...")
    beacon_manager = BeaconManager()
    logger.debug("Initialized BCM!!")

    logger.debug("Getting beacon configuration...")
    logger.debug("Displaying config data...:\n" + repr(beacon_manager.get_config()))
    
    beacon_manager.change_mode(BCM_MODE_Enum.BCM_MOD_Transparent)
    logger.debug("Changed mode to transparent!")
    logger.debug("Getting beacon state...")
    bcm_state = beacon_manager.check_state()
    logger.debug(bcm_state)

    logger.debug("Starting BST...")
    beacon_manager.start_bst(0x00D0, 0xBA00, [0x01])
    
    logger.debug("No errors occurred: BST started!")
    logger.debug("We now create a task that logs some text to the console upon receiving a callback...")
    event_thread = threading.Thread(target = beacon_manager.display_cb_event_trigger)
    event_thread.start()
    logger.debug("Number of threads: " + str(threading.active_count()))
    
    logger.debug("We now spawn a thread to get the VST")
    vst_result = 0
    vst_thread = threading.Thread(target = beacon_manager.wait_for_vst)
    vst_thread.start()

    logger.info("We now wait on the main thread until we receive a VST...")
    beacon_manager.wait_for_vst()

    logger.debug("Last VST details in raw bytes format:")
    logger.debug(beacon_manager.last_vst)
    logger.debug("We now decode the VST")
    vst_data = custom_der_decoders.decode_vst(beacon_manager.last_vst, logger)
    logger.debug(vst_data)

    logger.debug("We now send a SetMMI command on the main Thread to close the transaction")
    beacon_manager.set_mmi(True)

# Main execution
if __name__ == "__main__":
    main_thread = threading.Thread(target=main)
    main_thread.start()
