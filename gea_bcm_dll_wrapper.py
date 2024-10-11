import ctypes
from ctypes import POINTER, wintypes, c_char_p, c_uint, c_int, c_byte, c_bool, c_ulong, c_ushort, c_void_p
from ctypes.wintypes import HWND, LPCWSTR, UINT, BYTE, WORD, DWORD, CHAR, BOOL, LPVOID, LPBYTE

import json
import threading
import logging

gea_dll_loader_logger = logging.getLogger(__name__)

# Porting the GEA BCM DLL to Python. It mainly consisting of enums and foreign functions
# Function prototypes are callables that return foreign functions when called with a long pointer address, LPFN, as argument

# Define the BCM_ERR enum
class BCM_ERR_Enum(ctypes.c_int):
    # Layer 7 error codes
    BCM_CdeRefused = 0x01
    BCM_TrxInProgress = 0x02
    BCM_PbBeacon = 0x03
    BCM_TmoOBE = 0x09
    BCM_ResetBeacon = 0x0A
    BCM_PbParam = 0x0B
    BCM_PbFichConfig = 0x0C
    BCM_NotConfig = 0x1D
    
    # Additional BeaconManager error codes
    BCM_NoError = 0
    BCM_BadParameter = -100
    BCM_MemoryError = -101
    BCM_Busy = -104
    BCM_Collision = -105
    BCM_CommunicationAborted = -106
    BCM_CommunicationTimeout = -107
    BCM_ErrorResponse = -108
    BCM_ErrorCreatingEvent = -120
    BCM_ErrorCreatingMutex = -121
    BCM_ErrorCreatingTimer = -122
    BCM_EventError = -123
    BCM_CommunicationBadParameter = -1000
    BCM_PortNotActive = -1001
    BCM_PortFrozen = -1002
    BCM_PortOutputBusy = -1003
    BCM_ErrorCreatingBuffer = -1004
    BCM_CommunicationErrorCreatingEvent = -1005
    BCM_ErrorCreatingThread = -1006
    BCM_ErrorSettingPriority = -1007
    BCM_ErrorSettingEvent = -1008
    BCM_PortTypeError = -1009
    BCM_PortOpenError = -1010
    BCM_PortConfigurationError = -1011
    BCM_PortCloseError = -1012
    BCM_PortReadError = -1013
    BCM_PortWriteError = -1014
    BCM_PortEventError = -1015
    BCM_SocketBadParameter = -1050
    BCM_SocketErrorCreatingBuffer = -1051
    BCM_SocketErrorCreatingEvent = -1052
    BCM_SocketErrorCreatingThread = -1053
    BCM_SocketEventSelectError = -1054
    BCM_SocketWaitEventError = -1055
    BCM_SocketSetEventError = -1056
    BCM_SocketNotConnected = -1057
    BCM_SocketBufferFull = -1058
    BCM_SocketStartupError = -1061
    BCM_SocketCleanupError = -1062
    BCM_SocketCreateError = -1063
    BCM_SocketOptionError = -1064
    BCM_SocketControlError = -1065
    BCM_SocketBindError = -1066
    BCM_SocketListenError = -1067
    BCM_SocketAcceptEventError = -1068
    BCM_SocketAcceptError = -1069
    BCM_SocketConnectEventError = -1070
    BCM_SocketConnectError = -1071
    BCM_SocketSendEventError = -1072
    BCM_SocketSendError = -1073
    BCM_SocketReceiveEventError = -1074
    BCM_SocketReceiveError = -1075
    BCM_SocketShutdownError = -1076
    BCM_SocketCloseEventError = -1077
    BCM_SocketCloseError = -1078
    BCM_SocketCloseTimeoutError = -1079
    BCM_SocketGetHostError = -1080

    CUSTOM_COULD_NOT_CONNECT_VIA_TCP_IP = 10060

class BCMError:
    errors = {
        None: "No error",
        0: "No error",
        
        # Layer 7 errors
        0x01: "Command refused because the operating mode is not correct, or because the datagram sent is not correct",
        0x02: "Command refused because there is a transaction in progress",
        0x03: "Command refused because the beacon is out of order and the mode requested is not BCM_MOD_Stopped",
        0x09: "The beacon has lost the OBE.",
        0x0A: "The beacon has been reset.",
        0x0B: "Command refused because a parameter is not correct",
        0x0C: "Problem on the configuration file?",
        0x1D: "Command refused because the beacon has not been configured",
        
        # Beacon Manager errors
        -100: "Bad parameter",
        -101: "Memory error",
        -104: "Busy",
        -105: "Collision",
        -106: "Communication aborted",
        -107: "Communication timeout",
        -108: "Error response",
        -120: "Error creating event",
        -121: "Error creating mutex",
        -122: "Error creating timer",
        -123: "Event error",
        -1000: "Communication bad parameter",
        -1001: "Port not active",
        -1002: "Port frozen",
        -1003: "Port output busy",
        -1004: "Error creating buffer",
        -1005: "Communication error creating event",
        -1006: "Error creating thread",
        -1007: "Error setting priority",
        -1008: "Error setting event",
        -1009: "Port type error",
        -1010: "Port open error. This could mean the beacon is not connected or already in use.",
        -1011: "Port configuration error",
        -1012: "Port close error",
        -1013: "Port read error",
        -1014: "Port write error",
        -1015: "Port event error",
        -1050: "Socket bad parameter",
        -1051: "Socket error creating buffer",
        -1052: "Socket error creating event",
        -1053: "Socket error creating thread",
        -1054: "Socket event select error",
        -1055: "Socket wait event error",
        -1056: "Socket set event error",
        -1057: "Socket not connected",
        -1058: "Socket buffer full",
        -1061: "Socket startup error",
        -1062: "Socket cleanup error",
        -1063: "Socket create error",
        -1064: "Socket option error",
        -1065: "Socket control error",
        -1066: "Socket bind error",
        -1067: "Socket listen error",
        -1068: "Socket accept event error",
        -1069: "Socket accept error",
        -1070: "Socket connect event error",
        -1071: "Socket connect error",
        -1072: "Socket send event error",
        -1073: "Socket send error",
        -1074: "Socket receive event error",
        -1075: "Socket receive error",
        -1076: "Socket shutdown error",
        -1077: "Socket close event error",
        -1078: "Socket close error",
        -1079: "Socket close timeout error",
        -1080: "Socket get host error",

        10060: "CUSTOM: Couldn't connect via the TCP/IP. Check the provided ip and tcp port addresses.\n"
        "Reminder: TGB v2 has no TCP/IP support"
    }
    
    def get_error_description(error_code):
        return BCMError.errors.get(error_code, "Unknown error or no description")

# Define necessary types from ctypes and wintypes
BCM_ERR = c_int

# Define enums for several constants
class BCM_BST_TYPE_Enum:
    BCM_BST_ChangeBID = 0x03
    BCM_BST_Normal = 0x17

class BCM_MODE_Enum:
    BCM_MOD_Stopped = 0x00
    BCM_MOD_Transparent = 0x01
    BCM_MOD_Maintenance = 0x03

class BCM_RST_Enum:
    BCM_RST_BEACON = 0x01
    BCM_RST_ATL = 0x02

class BCM_CFG_Enum:
    BCM_CFG_Immediate = 0x00
    BCM_CFG_Reset = 0x01

class BCM_FREQ_Enum:
    BCM_CFG_F1 = 0x01
    BCM_CFG_F2 = 0x02
    BCM_CFG_F3 = 0x03
    BCM_CFG_F4 = 0x04

class BCM_SIZEMAX_Enum:
    BCM_SIZEMAX_BST = 121
    BCM_SIZEMAX_CMD = 118
    BCM_SIZEMAX_ANSWER = 122
    
class BCM_FIXED_SIZES_Enum:
    BCM_SIZE_CONFIG = 28
    BCM_SIZE_BEACONID = 6
    BCM_SIZE_ATLIO = 4

class BaudRate_Enum:
    BCM_CFG_1200 = 0x00
    BCM_CFG_2400 = 0x01
    BCM_CFG_4800 = 0x02
    BCM_CFG_9600 = 0x03
    BCM_CFG_19200 = 0x04
    BCM_CFG_38400 = 0x05
    BCM_CFG_57600 = 0x06
    BCM_CFG_115200 = 0x07

BCM_STATION = c_int
class BCM_STATION_Enum:
    BCM_Primary = 0
    BCM_Secondary = 1

BCM_CALLBACK = c_int
class BCM_CALLBACK_Enum:
    BCM_CB_IN = 0
    BCM_CB_ERR = 3

class BCM_Callback:
    cb_codes = {
        0: "Callback IN! A VST has been received!",
        3: "Callback Error occurred! Check the callback function's third argument. It contains the error code."
    }

    def get_description(callback_code):
        return BCM_Callback.cb_codes.get(callback_code, "Unknown callback code")

BCM_ALARMS = c_int
class BCM_ALARMS_Enum:
    BCM_AlarmPeriph = 1
    BCM_AlarmBeacon = 2
    BCM_EventReset = 3
    BCM_EventPollingOK = 4
    BCM_NotifyATLIO = 5
    
class BCM_Alarm:
    al_codes = {
        # Alarm code 1 is always enabled
        1: "The beacon is not connected!",
        # The following alarms are only sent if the beacon state polling is enabled (argCheckBeacon > 0)
        2: "The beacon is out of order!",
        3: "The beacon has been reset!",
        # This last alarm is only sent if argSendEvtPollingOK is set to True
        4: "The beacon is OK"
    }

    def get_description(alarm_code):
        return BCM_Alarm.al_codes.get(alarm_code, "Unknown alarm code")
# Define the necessary structures based on the specs and BeaconManager.h

# Define a pointer to the ST_BCM_REG structure
#ST_BCM_REG_PTR = LPVOID

class ST_BCM_REG(ctypes.Structure):
    pass
ST_BCM_REG_PTR = POINTER(ST_BCM_REG)

class ST_BCM_STATE(ctypes.Structure):
    _fields_ = [("state", BYTE),
                ("mode", BYTE),
                ("trxInProgress", BYTE)]
    
    def __iter__(self):
        return iter([(field_name, getattr(self, field_name)) for field_name, value in self._fields_])

    def __repr__(self):
        return repr(dict(self))
    
    def get_description(self):
        str_state = f"BCM_STATE:\n"
        if self.state == BCM_ERR_Enum.BCM_NoError:
            str_state += f"  State: OK\n"
        if self.state == BCM_ERR_Enum.BCM_PbBeacon:
            str_state += f"  State: The beacon is out of order\n"
        if self.state == BCM_ERR_Enum.BCM_ResetBeacon:
            str_state += f"  State: The beacon has been reset\n"
            
        if self.mode == BCM_MODE_Enum.BCM_MOD_Stopped:
            str_state += f"  Mode: Stopped. To switch off the HF, and to read or change the parameters of the beacon.\n"
        if self.mode == BCM_MODE_Enum.BCM_MOD_Transparent:
            str_state += f"  State: Transaction. To allow a transation\n"
        if self.mode == BCM_MODE_Enum.BCM_MOD_Transparent:
            str_state += f"  State: Maintenant. The beacon should not be used!\n"
            
        if self.trxInProgress == True:
            str_state += f"  Transaction: True. There is a transaction in progress.\n"
        else:
            str_state += f"  Transaction: False.\n"
        return str_state
ST_BCM_STATE_PTR = POINTER(ST_BCM_STATE)

class ST_BCM_CONFIG(ctypes.Structure):
    _fields_ = [("version", BYTE * 256),
                ("manufacturerID", WORD),
                ("individualID", DWORD),
                ("versionDescam", WORD),
                ("nbRetriesBST", WORD),
                ("timeoutRetryBST", WORD),
                ("nbRetriesACn", WORD),
                ("frequency", BYTE),
                ("baudRate", WORD),
                ("watchdog", WORD),
                ("technology", WORD),
                ("nbBeacons", BYTE),
                ("numLocation", WORD),
                ("dummy", BYTE * 4)]
    def __repr__(self):
        str_config = f"<ST_BCM_CONFIG:\n"
        
        for field_name, field_type in self._fields_:
            if field_name == "version":
                # Version is an ASCII-encoded NULL-terminated string
                str_config += f"  version: {bytes(self.version).decode("ascii").split("\x00")[0]}\n"
                continue
            if field_name == "dummy":
                # Dummy is 4-bytes variable free to be set by the user
                str_config += f"  dummy: {self.dummy[:]}\n"
                continue
            str_config += f"  {field_name}: {getattr(self, field_name)}\n"
        str_config += f">"
        
        return str_config

ST_BCM_CONFIG_PTR = POINTER(ST_BCM_CONFIG)

# Function prototype for callbacks
BCM_CB_HANDLER = ctypes.WINFUNCTYPE(None,
                                    ST_BCM_REG_PTR,
                                    BCM_CALLBACK,
                                    DWORD)

# Function prototype for alarms
BCM_ALARM_HANDLER = ctypes.WINFUNCTYPE(None,
                                    ST_BCM_REG_PTR,
                                    BCM_ALARMS,
                                    DWORD)

# Load the DLL
gea_dll_loader_logger.debug("Loading BeaconManager.dll...")
beacon_manager_dll = ctypes.windll.kernel32.LoadLibraryW("BeaconManager.dll")
getProcAddress = ctypes.windll.kernel32.GetProcAddress

# Function prototypes
# These are functions that take a pointer of a function
BCM_LPFN_GetLibVersion = ctypes.WINFUNCTYPE(DWORD)
BCM_LPFN_InitManagerWND = ctypes.WINFUNCTYPE(BCM_ERR,
                                             POINTER(ST_BCM_REG_PTR),
                                             DWORD,
                                             LPVOID,
                                             BYTE,
                                             BYTE,
                                             BCM_STATION,
                                             DWORD,
                                             c_bool,
                                             UINT,
                                             wintypes.HWND)
BCM_LPFN_InitManagerTHD = ctypes.WINFUNCTYPE(BCM_ERR,
                                             POINTER(ST_BCM_REG_PTR),
                                             DWORD,
                                             LPVOID,
                                             BYTE,
                                             BYTE,
                                             BCM_STATION,
                                             DWORD,
                                             c_bool,
                                             UINT,
                                             DWORD)
BCM_LPFN_InitManagerFNC = ctypes.WINFUNCTYPE(BCM_ERR,
                                             POINTER(ST_BCM_REG_PTR),
                                             DWORD,
                                             LPVOID,
                                             BYTE,
                                             BYTE,
                                             BCM_STATION,
                                             DWORD,
                                             c_bool,
                                             BCM_CB_HANDLER,
                                             BCM_ALARM_HANDLER)
BCM_LPFN_InitManagerWND_IP = ctypes.WINFUNCTYPE(BCM_ERR,
                                                POINTER(ST_BCM_REG_PTR),
                                                DWORD,
                                                LPVOID,
                                                POINTER(CHAR),
                                                WORD,
                                                BCM_STATION,
                                                DWORD,
                                                c_bool,
                                                UINT,
                                                wintypes.HWND)
BCM_LPFN_InitManagerTHD_IP = ctypes.WINFUNCTYPE(BCM_ERR,
                                                POINTER(ST_BCM_REG_PTR),
                                                DWORD,
                                                LPVOID,
                                                POINTER(CHAR),
                                                WORD,
                                                BCM_STATION,
                                                DWORD,
                                                c_bool,
                                                UINT,
                                                DWORD)
BCM_LPFN_InitManagerFNC_IP = ctypes.WINFUNCTYPE(BCM_ERR,
                                                POINTER(ST_BCM_REG_PTR),
                                                DWORD,
                                                LPVOID,
                                                POINTER(CHAR),
                                                WORD,
                                                BCM_STATION,
                                                DWORD,
                                                c_bool,
                                                BCM_CB_HANDLER,
                                                BCM_ALARM_HANDLER)
BCM_LPFN_CloseManager = ctypes.WINFUNCTYPE(BCM_ERR, POINTER(ST_BCM_REG_PTR))
BCM_LPFN_ChangeMode = ctypes.WINFUNCTYPE(BCM_ERR, ST_BCM_REG_PTR, BYTE)
BCM_LPFN_StartBST = ctypes.WINFUNCTYPE(BCM_ERR,
                                       ST_BCM_REG_PTR,
                                       POINTER(BYTE),
                                       DWORD,
                                       BYTE)
BCM_LPFN_GetVST = ctypes.WINFUNCTYPE(BCM_ERR,
                                     ST_BCM_REG_PTR,
                                     POINTER(BYTE),
                                     POINTER(DWORD),
                                     DWORD)
BCM_LPFN_GetUserParams = ctypes.WINFUNCTYPE(BCM_ERR,
                                             ST_BCM_REG_PTR,
                                             POINTER(DWORD),
                                             POINTER(LPVOID))
BCM_LPFN_SendCmd = ctypes.WINFUNCTYPE(BCM_ERR,
                                      ST_BCM_REG_PTR,
                                      POINTER(BYTE),
                                      DWORD,
                                      POINTER(BYTE),
                                      POINTER(DWORD),
                                      DWORD,
                                      BOOL)
BCM_LPFN_StopBST = ctypes.WINFUNCTYPE(BCM_ERR, ST_BCM_REG_PTR)
BCM_LPFN_CheckState = ctypes.WINFUNCTYPE(BCM_ERR,
                                         ST_BCM_REG_PTR,
                                         ST_BCM_STATE_PTR)
BCM_LPFN_Reset = ctypes.WINFUNCTYPE(BCM_ERR, ST_BCM_REG_PTR)
BCM_LPFN_ResetEx = ctypes.WINFUNCTYPE(BCM_ERR, ST_BCM_REG_PTR, BYTE)
BCM_LPFN_SetConfig = ctypes.WINFUNCTYPE(BCM_ERR,
                                         POINTER(ST_BCM_REG_PTR),
                                         BYTE,
                                         BYTE,
                                         BYTE)
BCM_LPFN_GetConfig = ctypes.WINFUNCTYPE(BCM_ERR,
                                         ST_BCM_REG_PTR,
                                         ST_BCM_CONFIG_PTR)
BCM_LPFN_GetBeaconID = ctypes.WINFUNCTYPE(BCM_ERR,
                                           ST_BCM_REG_PTR,
                                           POINTER(BYTE))
BCM_LPFN_GetATLIO = ctypes.WINFUNCTYPE(BCM_ERR,
                                        POINTER(ST_BCM_REG_PTR),
                                        POINTER(DWORD))

# Get the addresses of the long pointers to the foreign functions, LPFNs
gea_dll_loader_logger.debug("Getting the pointers to the addresses of the DLL's foreign functions...")

BCM_GetLibVersion_ptr = getProcAddress(beacon_manager_dll, b"BCM_GetLibVersion")

BCM_InitManagerWND_ptr = getProcAddress(beacon_manager_dll, b"BCM_InitManagerWND")
BCM_InitManagerTHD_ptr = getProcAddress(beacon_manager_dll, b"BCM_InitManagerTHD")
BCM_InitManagerFNC_ptr = getProcAddress(beacon_manager_dll, b"BCM_InitManagerFNC")
BCM_InitManagerWND_IP_ptr = getProcAddress(beacon_manager_dll, b"BCM_InitManagerWND_IP")
BCM_InitManagerTHD_IP_ptr = getProcAddress(beacon_manager_dll, b"BCM_InitManagerTHD_IP")
BCM_InitManagerFNC_IP_ptr = getProcAddress(beacon_manager_dll, b"BCM_InitManagerFNC_IP")

BCM_CloseManager_ptr = getProcAddress(beacon_manager_dll, b"BCM_CloseManager")
BCM_ChangeMode_ptr = getProcAddress(beacon_manager_dll, b"BCM_ChangeMode")
BCM_StartBST_ptr = getProcAddress(beacon_manager_dll, b"BCM_StartBST")
BCM_GetVST_ptr = getProcAddress(beacon_manager_dll, b"BCM_GetVST")
BCM_GetUserParams_ptr = getProcAddress(beacon_manager_dll, b"BCM_GetUserParams")
BCM_SendCmd_ptr = getProcAddress(beacon_manager_dll, b"BCM_SendCmd")
BCM_StopBST_ptr = getProcAddress(beacon_manager_dll, b"BCM_StopBST")
BCM_CheckState_ptr = getProcAddress(beacon_manager_dll, b"BCM_CheckState")
BCM_Reset_ptr = getProcAddress(beacon_manager_dll, b"BCM_Reset")
BCM_ResetEx_ptr = getProcAddress(beacon_manager_dll, b"BCM_ResetEx")
BCM_SetConfig_ptr = getProcAddress(beacon_manager_dll, b"BCM_SetConfig")
BCM_GetConfig_ptr = getProcAddress(beacon_manager_dll, b"BCM_GetConfig")
BCM_GetBeaconID_ptr = getProcAddress(beacon_manager_dll, b"BCM_GetBeaconID")
BCM_GetATLIO_ptr = getProcAddress(beacon_manager_dll, b"BCM_GetATLIO")

# Instantiating function prototypes
gea_dll_loader_logger.debug("Instantiating the ctypes function prototypes (to get Python callables)...")

get_lib_version = BCM_LPFN_GetLibVersion(BCM_GetLibVersion_ptr)

bcm_init_manager_wnd = BCM_LPFN_InitManagerWND(BCM_InitManagerWND_ptr)
bcm_init_manager_thd = BCM_LPFN_InitManagerTHD(BCM_InitManagerTHD_ptr)
bcm_init_manager_fnc = BCM_LPFN_InitManagerFNC(BCM_InitManagerFNC_ptr)
bcm_init_manager_wnd_ip = BCM_LPFN_InitManagerWND_IP(BCM_InitManagerWND_IP_ptr)
bcm_init_manager_thd_ip = BCM_LPFN_InitManagerTHD_IP(BCM_InitManagerTHD_IP_ptr)
bcm_init_manager_fnc_ip = BCM_LPFN_InitManagerFNC_IP(BCM_InitManagerFNC_IP_ptr)

bcm_close_manager = BCM_LPFN_CloseManager(BCM_CloseManager_ptr)
bcm_change_mode = BCM_LPFN_ChangeMode(BCM_ChangeMode_ptr)
bcm_start_bst = BCM_LPFN_StartBST(BCM_StartBST_ptr)
bcm_get_vst = BCM_LPFN_GetVST(BCM_GetVST_ptr)
bcm_get_user_params = BCM_LPFN_GetUserParams(BCM_GetUserParams_ptr)
bcm_send_cmd = BCM_LPFN_SendCmd(BCM_SendCmd_ptr)
bcm_stop_bst = BCM_LPFN_StopBST(BCM_StopBST_ptr)
bcm_check_state = BCM_LPFN_CheckState(BCM_CheckState_ptr)
bcm_reset = BCM_LPFN_Reset(BCM_Reset_ptr)
bcm_reset_ex = BCM_LPFN_ResetEx(BCM_ResetEx_ptr)
bcm_set_config = BCM_LPFN_SetConfig(BCM_SetConfig_ptr)
bcm_get_config = BCM_LPFN_GetConfig(BCM_GetConfig_ptr)
bcm_get_beacon_id = BCM_LPFN_GetBeaconID(BCM_GetBeaconID_ptr)
bcm_get_atlio = BCM_LPFN_GetATLIO(BCM_GetATLIO_ptr)

gea_dll_loader_logger.info("Getting the DLL version...")

bytes_dll_version = get_lib_version().to_bytes(4, 'big')
gea_dll_loader_logger.debug(bytes_dll_version)

gea_dll_loader_logger.info(f"Loaded DLL version: {bytes_dll_version[1]}.{bytes_dll_version[2]}.{bytes_dll_version[3]}")


from ASN.compiled_DSRC_instances import CCCv4_1 as CCC2019
from ASN.compiled_DSRC_instances import EFCv10_1 as EFC
from ASN.compiled_DSRC_instances import LACv2_1

import time

gea_dll_wrapper_logger = logging.getLogger(__name__)

with open('settings/beacon_manager_config.json', 'r') as beacon_manager_settings_file:
    beacon_manager_settings = json.load(beacon_manager_settings_file)

class BeaconError(Exception):
    pass
def bcm_error_wrapper(bcm_error: BCMError):
    if not isinstance(bcm_error, int):
        raise TypeError(bcm_error)
    if bcm_error != BCM_ERR_Enum.BCM_NoError:
        gea_dll_wrapper_logger.error(f"Beacon Manager Error {bcm_error}: {BCMError.get_error_description(bcm_error)}")

        # Handle error case if needed
        if bcm_error == BCM_ERR_Enum.BCM_TrxInProgress:
            gea_dll_wrapper_logger.error(f"Cannot execute function because a transaction is in progress!")
        raise BeaconError(f"{bcm_error}: {BCMError.get_error_description(bcm_error)}")

def cb_error_handler(callback_code, error_code):
    if callback_code == BCM_CALLBACK_Enum.BCM_CB_ERR:
        gea_dll_wrapper_logger.error(BCM_Callback.get_description(callback_code))
        # No Exception/Error is raised on callbacks.
        # We only log them
        gea_dll_wrapper_logger.error(f"Callback Error ({callback_code}), with BCM error code {error_code}")
        bcm_error_wrapper(error_code)

# Defining the BeaconManager class
class BeaconManager:
    def __init__(self, serial_port=None, beacon_alarm_state_polling_ms=1000, external_callback:callable = None, external_alarm:callable = None):
        self.beacon_state_ok_trigger = threading.Event()
        self.no_transaction_in_progress = threading.Event()
        self.callback_received_notifier = threading.Condition()
        self.transaction_lock = threading.Lock()
        self.transaction_in_progress = False

        self.external_callback = external_callback
        self.external_alarm = external_alarm

        # This is the BCM structure pointer. It is managed by the DLL
        self.reg_ptr = ST_BCM_REG_PTR()
        # This is the BCM state pointer. It is managed by the DLL
        self.beacon_state = ST_BCM_STATE()
        # Last received VST
        self.last_vst = bytes()
        self.last_vst_obj = {}
        
        # PDU cannot be 0 or 1
        pdu = 0x2
        # PDU is at most 4 bits
        pdu &= 0xF
        # The fragmentation header is 0b1xxxx001, where xxxx is the PDU
        self.frag_header = bytes([0x81 | (pdu << 3)])
        
        self.c_callback = BCM_CB_HANDLER(self.bcm_callback)
        self.c_alarm = BCM_ALARM_HANDLER(self.bcm_alarm)
        
        gea_dll_wrapper_logger.debug("Initializing GEA BCM...")
        
        send_event_polling_OK = False
        if beacon_alarm_state_polling_ms > 0:
            send_event_polling_OK = True
        # The user registration number is not used internally by the BCM DLL
        # It is thus free for use in our application
        user_registration = 7
        user_params = None

        gea_dll_wrapper_logger.debug(f"Current beacon manager settings in moment of initialization: {json.dumps(beacon_manager_settings, indent=2)}")
        beacon_name = beacon_manager_settings["chosen_beacon_name"]
        beacon_settings = beacon_manager_settings["TGBV"]
        if beacon_settings["communication_mode"] == "serial":
            if serial_port is None:
                serial_port = beacon_settings["serial_config"]["beacon_serial_port"]
            gea_dll_wrapper_logger.info(f"Beacon serial port: {serial_port}")
            serial_port_speed = BaudRate_Enum.BCM_CFG_115200
            result = bcm_init_manager_fnc(
                ctypes.byref(self.reg_ptr),
                user_registration,
                user_params,
                serial_port,
                serial_port_speed,
                BCM_STATION_Enum.BCM_Secondary,
                beacon_alarm_state_polling_ms,
                send_event_polling_OK,
                self.c_callback,
                self.c_alarm
            )
        else:
            beacon_ip_address_bytes = beacon_settings["tcp_ip_config"]["ip_address"].encode('utf-8')
            beacon_tcp_port = beacon_settings["tcp_ip_config"]["tcp_port"]

            result = bcm_init_manager_fnc_ip(
                ctypes.byref(self.reg_ptr),
                user_registration,
                user_params,
                beacon_ip_address_bytes,
                beacon_tcp_port,
                BCM_STATION_Enum.BCM_Secondary,
                beacon_alarm_state_polling_ms,
                send_event_polling_OK,
                self.c_callback,
                self.c_alarm
            )

        bcm_error_wrapper(result)
        self.update_beacon_id()
        self.handle_init_errors()
    
    def update_beacon_id(self) -> EFC.EfcDsrcGeneric.BeaconID:
        gea_dll_wrapper_logger.debug("Getting Beacon ID...")
        
        beacon_id_buffer_array = ctypes.create_string_buffer(BCM_FIXED_SIZES_Enum.BCM_SIZE_BEACONID)

        # Pointer where the BeaconID will be stored by BCM
        lp_beacon_id = ctypes.cast(beacon_id_buffer_array, POINTER(BYTE))

        bcm_get_beacon_id(self.reg_ptr, lp_beacon_id)
        self.last_beacon_id = bytes(beacon_id_buffer_array[0:BCM_FIXED_SIZES_Enum.BCM_SIZE_BEACONID])

        gea_dll_wrapper_logger.debug(f"Latest Beacon ID in hex: {self.last_beacon_id.hex().upper()}")
        return self.last_beacon_id
    
    # Defining the Callback and Alarm default functions (they are both callback functions)
    # But alarm has a state
    # As those callback functions are directly called by the internal thread which is
    # managing the communication with the beacon they should return as
    # quickly as possible
    def bcm_callback(self, reg_ptr, callback_type, error_code):
        gea_dll_wrapper_logger.debug("CB: Callback notification received!")
        if callable(self.external_callback):
            gea_dll_wrapper_logger.debug("CB: External callback function present! (from the frontend, for exemple)")
            gea_dll_wrapper_logger.debug("CB: We now call/notify it!")
            self.external_callback(callback_type, error_code)

        try:
            cb_error_handler(callback_type, error_code)
            bcm_error_wrapper(error_code)
            gea_dll_wrapper_logger.debug("CB: OK! No error occurred in callback: This means a VST was received!")
            gea_dll_wrapper_logger.debug("CB: We thus notify all threads waiting on the callback_received_notifier condition")
            with self.callback_received_notifier:
                self.callback_received_notifier.notify_all()
        except:
            gea_dll_wrapper_logger.error(f"CB: Error, with BCM error code {error_code}")
            return
    def bcm_alarm(self, reg_ptr, alarm_type, alarm_state):
        gea_dll_wrapper_logger.debug(f"AL: Alarm notification ({alarm_type}) received!")
        if callable(self.external_alarm):
            gea_dll_wrapper_logger.debug("AL: External alarm function present! (from the frontend, for exemple)")
            gea_dll_wrapper_logger.debug("AL: We now call/notify it!")
            self.external_alarm(alarm_type, alarm_state)

        if alarm_type == BCM_ALARMS_Enum.BCM_AlarmPeriph or alarm_type == BCM_ALARMS_Enum.BCM_AlarmBeacon:
            gea_dll_wrapper_logger.error(f"Error in Alarm! Description: {BCM_Alarm.get_description(alarm_type)}")
            return
        gea_dll_wrapper_logger.debug(f"Alarm description: {BCM_Alarm.get_description(alarm_type)}")
        if alarm_type == BCM_ALARMS_Enum.BCM_EventPollingOK:
            self.beacon_state_ok_trigger.set()
        return
    def handle_init_errors(self):
        """This function handles initialization issues, like:
            Unclosed transactions
            Beacon not in stopped mode
            etc."""

        gea_dll_wrapper_logger.debug("Trying get the updated beacon's state...")
        gea_dll_wrapper_logger.debug("Trying get the updated beacon's state...")
        result = self.update_state()

        gea_dll_wrapper_logger.debug(f"Beacon State iterator keys: {list(iter(self.beacon_state))}")
        gea_dll_wrapper_logger.debug(f"Beacon State iterator keys: {list(iter(self.beacon_state))}")
        gea_dll_wrapper_logger.debug(self.beacon_state)

        if result == BCM_ERR_Enum.BCM_NoError:
            pass
        elif result == BCM_ERR_Enum.BCM_SocketNotConnected:
            gea_dll_wrapper_logger.error("Wait for socket to connect before sending commands!")
        else:
            gea_dll_wrapper_logger.error("We could not handle the error, so it will be raised")
            bcm_error_wrapper(result)
        
        self.wait_until_ok()

        gea_dll_wrapper_logger.debug("Updating beacon state (It should now be OK)...")
        result = self.update_state()

        # If a previous transaction was not closed, we forcefully reset the beacon
        if self.beacon_state.trxInProgress:
            gea_dll_wrapper_logger.error("Previously unclosed transaction in progress!")
            gea_dll_wrapper_logger.info("We will forcefully reset the beacon...")
            self.reset_manager()
            
            self.wait_until_ok()

        if self.beacon_state.mode != BCM_MODE_Enum.BCM_MOD_Stopped:
            self.change_mode(BCM_MODE_Enum.BCM_MOD_Stopped)
            gea_dll_wrapper_logger.debug("Changed operating mode to stopped!")
        self.update_state()
        return self.beacon_state

    def wait_until_ok(self):
        gea_dll_wrapper_logger.debug("Polling the beacon state until it is in an OK state...")
        self.beacon_state_ok_trigger.wait()
        gea_dll_wrapper_logger.debug("Beacon is OK!!!")

    def display_cb_event_trigger(self):
        gea_dll_wrapper_logger.debug("\tWaiting for CB notification...")
        with self.callback_received_notifier:
            self.callback_received_notifier.wait()
        gea_dll_wrapper_logger.debug("\tCB notification received!!! You can receive a VST now.")
        
    def update_state(self):
        gea_dll_wrapper_logger.debug(f"Udpating beacon state...")
        gea_dll_wrapper_logger.debug(f"Udpating beacon state...")
        if self.beacon_state.trxInProgress:
            gea_dll_wrapper_logger.error(f"Do not try to update the state: A transaction is in progress! Otherwise, an Exception will be raised.")
            return
        
        result = bcm_check_state(self.reg_ptr, ctypes.byref(self.beacon_state))
        bcm_error_wrapper(result)

        gea_dll_wrapper_logger.debug(f"Beacon state: {self.beacon_state}")
        return result
    def get_last_beacon_state(self):
        gea_dll_wrapper_logger.debug(f"Beacon state dict: {dict(self.beacon_state)}")
        # return vars(self.beacon_state)
        return dict(self.beacon_state)
        gea_dll_wrapper_logger.debug(f"Beacon state dict: {dict(self.beacon_state)}")
        # return vars(self.beacon_state)
        return dict(self.beacon_state)
    
    def get_config(self):
        bcm_config = ST_BCM_CONFIG()
        
        result = bcm_get_config(self.reg_ptr, ctypes.byref(bcm_config))
        bcm_error_wrapper(result)

        return bcm_config
    
    def change_mode(self, operating_mode_code):
        result = bcm_change_mode(self.reg_ptr, operating_mode_code)
        bcm_error_wrapper(result)
    def shutdown(self):
        result = bcm_close_manager(ctypes.byref(self.reg_ptr))
        bcm_error_wrapper(result)
        
    def reset_manager(self):
        result = bcm_reset(self.reg_ptr)
        bcm_error_wrapper(result)
    
    def initialization(self, manufacturer_id=0x31, individual_id=0x111, mandapplications=[1, 20, 29], profile=0x00, profile_list=[0x00], non_mand_applications = [], bst_type:int = BCM_BST_TYPE_Enum.BCM_BST_ChangeBID):
        if self.beacon_state.trxInProgress:
            gea_dll_wrapper_logger.error("Do not try to initilize a transaction! One is already in progress!")
            return
        gea_dll_wrapper_logger.debug("We lock the thread until the opened transaction is closed!")

        self.start_bst(manufacturer_id, individual_id, mandapplications, profile, profile_list, non_mand_applications, bst_type)
        gea_dll_wrapper_logger.debug("No errors occurred when starting BST!")
        
        gea_dll_wrapper_logger.info("We now wait on the main thread until we a VST notification is received...")
        self.wait_for_vst_notification()
        #self.no_transaction_in_progress.set()

        gea_dll_wrapper_logger.info("A VST notification was received! We now get the VST")
        fragmented_t_apdu_init_resp_datagram = self.get_vst()
        gea_dll_wrapper_logger.info(f"Fragmented T_APDU containing VST: {fragmented_t_apdu_init_resp_datagram.hex().upper()}")
        
        gea_dll_wrapper_logger.debug("We now remove the fragmentation header and instantiate an T_APDU object from the response!")
        t_apdu_init_resp_datagram = bytes(fragmented_t_apdu_init_resp_datagram[1:])
        EFC.EfcDsrcGeneric.T_APDUs.from_uper(t_apdu_init_resp_datagram)
        gea_dll_wrapper_logger.debug(f"T-APDU without fragmentation header: {t_apdu_init_resp_datagram}")
        
        gea_dll_wrapper_logger.debug("We now instantiate a T_APDU object from the response!")
        gea_dll_wrapper_logger.info(f"T_APDU containing VST in JER: {EFC.EfcDsrcGeneric.T_APDUs.to_jer()}")
        gea_dll_wrapper_logger.debug(f"Instantiated T_APDU object value: {EFC.EfcDsrcGeneric.T_APDUs._val}")
        gea_dll_wrapper_logger.info(f"Instantiated T_APDU in JER: {EFC.EfcDsrcGeneric.T_APDUs.to_jer()}")

        # Decoding VST
        gea_dll_wrapper_logger.debug("We now obtain the VST object from the T_APDU response!")
        gea_dll_wrapper_logger.debug("VST is a parameterized type, so we cannot decode/encode it, only the APDU!")
        self.last_vst_obj = EFC.EfcDsrcGeneric.T_APDUs._to_jval()["initialisation-response"]

        gea_dll_wrapper_logger.debug(f'Decoded VST: {self.last_vst_obj}')
        return self.last_vst_obj

    # Start sending a BST
    def start_bst(self, manufacturer_id=0x31, individual_id=0x111, mandapplications=[1, 20, 29], profile=0x00, profile_list=[0x00], non_mand_applications = [], bst_type:int = BCM_BST_TYPE_Enum.BCM_BST_ChangeBID):
        mandApplications = [{'aid': mandatory_aid} for mandatory_aid in mandapplications]
        # profileList = [{'profile': profile_id} for profile_id in profile_list]

        bst_value = {
            'rsu': {
                'manufacturerid': manufacturer_id,
                'individualid': individual_id
                },
            'time': int(time.time()),
            'profile': profile,
            'mandApplications': mandApplications,
            'profileList': profile_list
            }
        EFC.EfcDsrcGeneric.BST.set_val(bst_value)
        bst_datagram = EFC.EfcDsrcGeneric.BST.to_uper()
        gea_dll_wrapper_logger.debug(f"BST in UPER encoding in hex: {bst_datagram.hex().upper()}")

        EFC.EfcDsrcGeneric.T_APDUs.set_val(('initialisation-request', EFC.EfcDsrcGeneric.BST._val))
        gea_dll_wrapper_logger.debug(f"T_APDU containing BST in JER: {EFC.EfcDsrcGeneric.T_APDUs.to_jer()}")

        fragmented_t_apdu_init_req_datagram = self.frag_header + EFC.EfcDsrcGeneric.T_APDUs.to_uper()
        gea_dll_wrapper_logger.debug(f"Fragmented T_APDU containing BST: {fragmented_t_apdu_init_req_datagram.hex().upper()}")

        if len(bst_datagram) > BCM_SIZEMAX_Enum.BCM_SIZEMAX_BST:
            gea_dll_wrapper_logger.error(f"Datagram is too big! Will probably cause a BST error")
        result = self.start_bst_wrapper(fragmented_t_apdu_init_req_datagram, bst_type)

        gea_dll_wrapper_logger.debug("We now get the lastest BeaconID just after starting the BST")
        self.update_beacon_id()
        gea_dll_wrapper_logger.debug(f"Last BeaconID: {self.last_beacon_id.hex().upper()}")

        return result
        
    def start_bst_wrapper(self, bst_datagram:bytes, bst_type:int):
        bst_datagram_buffer = ctypes.create_string_buffer(bst_datagram, size=len(bst_datagram))
        # Pointer to the buffered BST datagram
        lp_bst_datagram = ctypes.cast(bst_datagram_buffer, POINTER(BYTE))
        byte_bst_type = BYTE(bst_type)
        gea_dll_wrapper_logger.info(f"BST to be sent in hex format: {bst_datagram.hex().upper()}")
        gea_dll_wrapper_logger.info(f"Decoded BST: {bst_datagram.hex().upper()}")

        result = bcm_start_bst(self.reg_ptr,
                               lp_bst_datagram,
                               DWORD(len(bst_datagram)),
                               byte_bst_type)
        bcm_error_wrapper(result)
        gea_dll_wrapper_logger.debug("No errors occurred: BST started!")
        st_bcm_reg_ptr_value = ctypes.cast(self.reg_ptr, ctypes.c_void_p).value
        #bcm_logger.debug(f"ST_BCM_REG (dereferenced value): {st_bcm_reg_ptr_value}")
        return result
        
    
    # Wait for the application to be notified through a callback
    def wait_for_vst_notification(self):
        with self.callback_received_notifier:
            self.callback_received_notifier.wait()

    # Wait for a notification then get the VST
    def wait_and_get_vst(self):
        self.wait_for_vst_notification()
        return self.get_vst()
    
    # Get the VST
    # This function should only be called inside the callback declared to the
    # BCM Init Manager
    def get_vst(self):
        gea_dll_wrapper_logger.debug("Getting VST...")
        
        dword_max_size = DWORD(BCM_SIZEMAX_Enum.BCM_SIZEMAX_ANSWER)
        vst_answer_buffer_array = ctypes.create_string_buffer(BCM_SIZEMAX_Enum.BCM_SIZEMAX_ANSWER)
        vst_answer_size = DWORD()

        # Pointer where the VST datagram answer will be stored by BCM
        lp_vst_response_datagram = ctypes.cast(vst_answer_buffer_array, POINTER(BYTE))
        
        result = bcm_get_vst(self.reg_ptr,
                             lp_vst_response_datagram,
                             ctypes.byref(vst_answer_size),
                             dword_max_size
                             )
        
        gea_dll_wrapper_logger.debug("Handling errors...")
        bcm_error_wrapper(result)
        gea_dll_wrapper_logger.debug("VST received!")

        # Slicing a ctypes array or pointer will automatically produce a Python list
        # We slice it at the given size, not the buffer's maximum size
        received_vst_list = lp_vst_response_datagram[:vst_answer_size.value]

        # Converting VST to bytes structure and storing it in last_vst attribute
        self.last_vst = bytes(received_vst_list)

        # Log the VST
        gea_dll_wrapper_logger.info(f"Received VST in hex format: {self.last_vst.hex().upper()}")
        return self.last_vst
    
    def send_command(self, datagram: bytes, close=False):
        lp_cmd_datagram = ctypes.cast(datagram, POINTER(BYTE))
        
        # Buffers and pointers for command response datagrams
        cmd_response_buffer_array = ctypes.create_string_buffer(BCM_SIZEMAX_Enum.BCM_SIZEMAX_CMD)
        dword_cmd_resonse_max_size = DWORD(BCM_SIZEMAX_Enum.BCM_SIZEMAX_CMD)
        lp_cmd_response_datagram = ctypes.cast(cmd_response_buffer_array, POINTER(BYTE))
        cmd_response_size = DWORD()

        gea_dll_wrapper_logger.debug(f"Command to be sent in hex format: {datagram.hex().upper()}")

        result = bcm_send_cmd(
            self.reg_ptr,
            lp_cmd_datagram,
            DWORD(len(datagram)),
            lp_cmd_response_datagram,
            ctypes.byref(cmd_response_size),
            dword_cmd_resonse_max_size,
            close
            )
        self.last_cmd_req = bytes(datagram)
        bcm_error_wrapper(result)

        # Iterating cmd response pointer to get its value/contents
        response_as_list = lp_cmd_response_datagram[:cmd_response_size.value]
        self.last_cmd_response = bytes(response_as_list)
        gea_dll_wrapper_logger.debug(f"Command response in hex format: {self.last_cmd_response.hex().upper()}")
        return self.last_cmd_response
    
    def send_req_t_apdu_and_obtain_resp_t_apdu(self, asn1_request_t_apdu_value, close=False) -> dict:
        gea_dll_wrapper_logger.debug(f"Preparing request T_APDU to be sent...")
        EFC.EfcDsrcGeneric.T_APDUs.set_val(asn1_request_t_apdu_value)
        gea_dll_wrapper_logger.debug(f"Request T_APDU value: {EFC.EfcDsrcGeneric.T_APDUs._val}")
        gea_dll_wrapper_logger.debug(f"T_APDU in JER: {EFC.EfcDsrcGeneric.T_APDUs.to_jer()}")
        fragmented_t_apdu = self.frag_header + EFC.EfcDsrcGeneric.T_APDUs.to_uper()

        gea_dll_wrapper_logger.info(f"Sending fragmented T_APDU: {fragmented_t_apdu.hex().upper()}")
        fragmented_t_apdu_with_get_response_bytes = self.send_command(fragmented_t_apdu, close)
        gea_dll_wrapper_logger.debug(f"Decoding received response T_APDU...")
        gea_dll_wrapper_logger.info(f"Fragmented T_APDU response obtained from beacon in hex (supposed to be UPER): {fragmented_t_apdu_with_get_response_bytes.hex().upper()}")
        t_apdu_with_get_response_bytes = bytes(fragmented_t_apdu_with_get_response_bytes[1:])

        EFC.EfcDsrcGeneric.T_APDUs.from_uper(t_apdu_with_get_response_bytes)
        gea_dll_wrapper_logger.debug(f"Response T_APDU value: {EFC.EfcDsrcGeneric.T_APDUs._val}")
        json_encoded_response_t_apdu = EFC.EfcDsrcGeneric.T_APDUs._to_jval()
        gea_dll_wrapper_logger.debug(f"Response T_APDU in JSON value: {json_encoded_response_t_apdu}")
        return json_encoded_response_t_apdu

    def get_eid_info(self, eid:int) -> int:
        vst_application_index = -1
        gea_dll_wrapper_logger.debug(f"Getting application with EID {eid}")
        for index, application in enumerate(self.last_vst_obj['applications']):
            gea_dll_wrapper_logger.debug(f"Application details: {application}")
            if application["eid"] == eid:
                vst_application_index = index
        if vst_application_index == -1:
            gea_dll_wrapper_logger.info(f"EID {eid} is not present!")
        else:
            gea_dll_wrapper_logger.debug(f"Index of EID {eid} on VST is {vst_application_index}")
        return vst_application_index
    
    def send_get_request(self, eid, accessCredentials=None, attrIdList=None, close = False) -> EFC.EfcDsrcGeneric.Get_Response:
        # Get.Request is filled with 1 bit valued at 0
        get_req_value = {
            'eid': eid,
            'accessCredentials': accessCredentials,
            'attrIdList': attrIdList,
            'fill': (0, 1)
        }
        # Ignore keys in dict that map to None!!
        get_req_value = {key: value for key, value in get_req_value.items() if value is not None}

        EFC.EfcDsrcGeneric.Get_Request.set_val(get_req_value)
        gea_dll_wrapper_logger.debug(f"Get.Request value: {EFC.EfcDsrcGeneric.Get_Request._val}")
        gea_dll_wrapper_logger.info(f"Get.Request in JER: {EFC.EfcDsrcGeneric.Get_Request.to_jer()}")

        asn1_request_t_apdu_value = ('get-request', get_req_value)
        json_encoded_response_t_apdu = self.send_req_t_apdu_and_obtain_resp_t_apdu(asn1_request_t_apdu_value)
        # Obtaining GET.response contents
        gea_dll_wrapper_logger.debug("We now obtain the VST object from the T_APDU response!")
        gea_dll_wrapper_logger.debug("GET.request is a parameterized type, so we cannot encode/decode it, only the T_APDU!")
        get_response = json_encoded_response_t_apdu['get-response']
        return get_response

    def presentation_request(self, eid:int, access_credentials:int, attribute_ids=[], operator_auk_ref=111, response_expected=True, close=False):
        return self.send_get_stamped_request(eid, access_credentials, attribute_ids, operator_auk_ref, response_expected, close)
    def send_get_stamped_request(self, eid:int, access_credentials:int, attribute_ids=[], operator_auk_ref=111, response_expected=True, close=False):
        datagram = self.get_stamped_request_datagram_preparation(eid, access_credentials, attribute_ids, operator_auk_ref, response_expected, close)
        return self.send_command(datagram)
    def get_stamped_request_datagram_preparation(self, eid:int, access_credentials:int, attribute_ids=[], operator_auk_ref=111, response_expected=True, close = False):
        gea_dll_wrapper_logger.debug(f"Preparing a GET_STAMPED.request to get attributes with ids {attribute_ids}")
        action_req_header = 0

        # The ActionParameter is always present in a GET_STAMPED request
        # Also, its container type/choice is set to 17 = 0x11 for a GetStampedRq
        action_req_header = action_req_header | 0b0100
        GetStampedRq_action_type = 0x11

        if response_expected:
            action_req_header = action_req_header | 1

        if access_credentials is not None:
            # Access Credentials is present!
            action_req_header = action_req_header | 0b1000
            # Length + Value
            ac_cr_list = [4] + list(access_credentials.to_bytes(4, 'big'))
        else:
            ac_cr_list = []

        # ActionParamater is always present, so AttributeIdList must be present even if just an empty list (thus with length = 0)
        if attribute_ids is None:
            attribute_ids = []
        if attribute_ids:
            # AttributeIdList is present!
            # Length + Value
            attribute_id_list = [len(attribute_ids)] + attribute_ids
        #else:
        #    attribute_id_list = [00]
        
        # ActionType is a GET_STAMPED
        action_type = 0
        # Attribute 0x20 = 32 is the PAN, or PaymentMeans
        # So the AttributeIdList is set by default to [0x20]

        self.rnd_rse = custom_ITS_per_decoders.encode_date_and_time()
        rnd_rse_list = [4] + list(self.rnd_rse.to_bytes(4, 'big'))
        presentation_request = [self.frag_header, action_req_header, eid, action_type] + ac_cr_list  + [GetStampedRq_action_type] + attribute_id_list + rnd_rse_list + [operator_auk_ref]
        
        gea_dll_wrapper_logger.debug(f"Presentation request: {presentation_request}")
        
        # Converting command request to bytes structure and returning it
        return bytes(presentation_request)

    def set_mmi(self, eid=0, set_mmi_request_value=0, close = False):
        gea_dll_wrapper_logger.debug(f"Preparing a SET_MMI.request")

        # SetMMI is a parameterized type, so it needs to be inside a container
        set_mmi_efc_container_value = ('setmmirq', set_mmi_request_value)
        EFC.EfcDsrcGeneric.EfcContainer.set_val(set_mmi_efc_container_value)
        gea_dll_wrapper_logger.debug(f"EfcContainer of Type 69 (SET_MMI) value decoded with JER: {EFC.EfcDsrcGeneric.EfcContainer.to_jer()}")
        gea_dll_wrapper_logger.debug(f"EfcContainer of Type 69 (SET_MMI) value decoded with PER: {EFC.EfcDsrcGeneric.EfcContainer.to_uper()}")
        
        # SetMMI ActionType is 0xA, or 10 in decimal
        set_mmi_action_request_val = {
            'mode': True,
            'eid': eid,
            'actionType': 0xA,
            'actionParameter': set_mmi_efc_container_value
            }
        
        t_apdu_with_set_mmi_action_req_value = ('action-request', set_mmi_action_request_val)
        gea_dll_wrapper_logger.info(f"ACTION.request of Type 10 (SET_MMI) being now sent...")

        t_apdu_with_action_response = self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_set_mmi_action_req_value, close)
        return t_apdu_with_action_response
    def decode_last_get_response(self):
        decoded_response = custom_ITS_per_decoders.decode_response(self.last_cmd_response)
        if decoded_response is None:
            return
        try:
            return_status = decoded_response["ReturnStatus"]
            raise(return_status)
        except custom_ITS_per_decoders.ReturnStatus:
            gea_dll_wrapper_logger.error(return_status.message)
        decoded_response

    def send_close_transaction_to_obu(self):
        command_response = self.set_mmi(True)
        self.no_transaction_in_progress.clear()
        return command_response
    def stopping(self):
        gea_dll_wrapper_logger.info(f"Stopping Beacon Manager!")
        # If a transaction is still open, we close it
        if self.beacon_state.trxInProgress:
            gea_dll_wrapper_logger.info(f"A transaction was in progress according to the DLL! Closing it...")
            self.send_close_transaction_to_obu()
        
        self.update_state()

        if self.beacon_state.mode != BCM_MODE_Enum.BCM_MOD_Stopped:
            self.change_mode(BCM_MODE_Enum.BCM_MOD_Stopped)
            gea_dll_wrapper_logger.debug("Changed mode to stopped!")