import threading
import logging
import custom_der_decoders

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from python_dll_loader import *
from BeaconManager import BeaconManager

root_logger = logging.getLogger()

console_handler = logging.StreamHandler()
console_formatter = logging.Formatter("%(levelname)-8s - %(threadName)s - %(message)s")
console_handler.setFormatter(console_formatter)

file_handler = logging.FileHandler('gea_bcm_dll_python_loader.log')
file_formatter = logging.Formatter("%(asctime)s - %(levelname)-8s - %(threadName)s - %(message)s")
file_handler.setFormatter(file_formatter)

root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)
root_logger.setLevel(logging.DEBUG)

def main():
    root_logger.debug("Instantiating BeaconManager class...")
    beacon_manager = BeaconManager()
    root_logger.debug("Initialized BCM!!")

    root_logger.debug("Getting beacon configuration...")
    root_logger.debug("Displaying config data...:\n" + repr(beacon_manager.get_config()))
    
    beacon_manager.change_mode(BCM_MODE_Enum.BCM_MOD_Transparent)
    root_logger.debug("Changed mode to transparent!")
    root_logger.debug("Getting beacon state...")
    bcm_state = beacon_manager.check_state()
    root_logger.debug(bcm_state)

    root_logger.debug("Starting BST...")
    beacon_manager.start_bst(0x00D0, 0xBA00, [0x01])
    
    root_logger.debug("No errors occurred: BST started!")
    root_logger.debug("We now create a task that logs some text to the console upon receiving a callback...")
    event_thread = threading.Thread(target = beacon_manager.display_cb_event_trigger)
    event_thread.start()
    root_logger.debug("Number of threads: " + str(threading.active_count()))

    root_logger.info("We now wait on the main thread until we receive a VST...")
    beacon_manager.wait_and_get_vst()

    root_logger.debug("Last VST details in raw bytes format:")
    root_logger.debug(beacon_manager.last_vst)
    root_logger.debug("We now decode the VST")
    vst_data = custom_der_decoders.decode_vst(beacon_manager.last_vst)
    root_logger.debug(vst_data)

    root_logger.debug("We should send a SetMMI command on the main Thread to close the transaction")
    root_logger.debug("Otherwise, the transaction will remain unclosed and cause an error on the next execution")
    #beacon_manager.set_mmi(True)


# Main execution
if __name__ == "__main__":
    main_thread = threading.Thread(target=main)
    main_thread.start()
