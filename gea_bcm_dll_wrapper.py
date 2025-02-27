import ctypes
from ctypes import POINTER, wintypes, c_char_p, c_uint, c_int, c_byte, c_bool, c_ulong, c_ushort, c_void_p
from ctypes.wintypes import HWND, LPCWSTR, UINT, BYTE, WORD, DWORD, CHAR, BOOL, LPVOID, LPBYTE

import logging

gea_dll_loader_logger = logging.getLogger(__name__ + ".loader")

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

error_descriptions = {
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

class BCMError:
    def __init__(self, error_code):
        self.error_code = error_code
    def get_error_description(self):
        return error_descriptions.get(self.error_code, "Unknown error or no description")

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

bcm_mode_descriptions = {
    BCM_MODE_Enum.BCM_MOD_Stopped: f"Mode: Stopped. To switch off the HF, and to read or change the parameters of the beacon.",
    BCM_MODE_Enum.BCM_MOD_Transparent: f"Mode: Transparent. The beacon can be used to communicate with a device",
    BCM_MODE_Enum.BCM_MOD_Maintenance: f"Mode: Maintenance. The beacon should not be used!"
}

class ST_BCM_STATE(ctypes.Structure):
    _fields_ = [("state", BYTE),
                ("mode", BYTE),
                ("trxInProgress", BYTE)]
    
    def __iter__(self):
        return iter([(field_name, getattr(self, field_name)) for field_name, value in self._fields_])

    def __repr__(self):
        return repr(dict(self))
    
    def get_description_json(self):
        return {
            'state': BCMError(self.state).get_error_description(),
            'mode': bcm_mode_descriptions[self.mode],
            'trxInProgress': self.trxInProgress
            }
    def get_description(self):
        return json.dumps(obj={
            'state': BCMError(self.state).get_error_description(),
            'mode': bcm_mode_descriptions[self.mode],
            'trxInProgress': self.trxInProgress
            }, indent=2)

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

import time
import json
import threading

gea_dll_wrapper_logger = logging.getLogger(__name__ + ".wrapper")

with open('settings/beacon_manager_config.json', 'r') as beacon_manager_settings_file:
    beacon_manager_settings = json.load(beacon_manager_settings_file)

class Layer7Exception(Exception):
    pass
def bcm_error_wrapper(bcm_error: BCMError):
    if not isinstance(bcm_error, int):
        raise TypeError(bcm_error)
    if bcm_error != BCM_ERR_Enum.BCM_NoError:
        gea_dll_wrapper_logger.error(f"Beacon Manager Error {bcm_error}: {BCMError(bcm_error).get_error_description()}")

        # Handle error case if needed
        if bcm_error == BCM_ERR_Enum.BCM_TrxInProgress:
            gea_dll_wrapper_logger.error(f"Cannot execute function because a transaction is in progress!")
        raise Layer7Exception(f"{bcm_error}: {BCMError(bcm_error).get_error_description()}")

def cb_error_handler(callback_code, error_code):
    if callback_code == BCM_CALLBACK_Enum.BCM_CB_ERR:
        gea_dll_wrapper_logger.error(BCM_Callback.get_description(callback_code))
        # No Exception/Error is raised on callbacks.
        # We only log them
        gea_dll_wrapper_logger.error(f"Callback Error ({callback_code}), with BCM error code {error_code}")
        bcm_error_wrapper(error_code)

available_baud_rate_enum_vals = {
    1200: 0x00,
    2400: 0x01,
    4800: 0x02,
    9600: 0x03,
    19200: 0x04,
    38400: 0x05,
    57600: 0x06,
    115200: 0x07
}

def set_beacon_name(beacon_name:str):
    """Sets the beacon name.
    This is used to find its corresponding configuration in the beacon config file"""
    global chosen_beacon_name

    chosen_beacon_name = beacon_name

# Defining the actual BCM (Beacon Manager) GEA DLL Python module wrapper functions
def initialize_gea_bcm_dll_wrapper(external_callback_param:callable = None, external_alarm_param:callable = None, serial_port=None):
    """Initialize PERTEL beacon manager.
    Remember to set the beacon's name beforehand!"""
    global chosen_beacon_name
    global beacon_state_ok_event
    global callback_received_event

    global frag_header

    global external_callback
    global external_alarm
    global c_callback
    global c_alarm

    global reg_ptr
    global beacon_state

    global last_vst
    global last_vst_obj

    print(chosen_beacon_name)
    if "chosen_beacon_name" not in globals():
        raise Exception("Beacon name was not set!!! We need that to get the correct configuration")
    # This is the BCM structure pointer. It is managed by the DLL
    reg_ptr = ST_BCM_REG_PTR()

    beacon_state_ok_event = threading.Event()
    callback_received_event = threading.Event()

    external_callback = external_callback_param
    external_alarm = external_alarm_param

    # This is the BCM state pointer. It is managed by the DLL
    beacon_state = ST_BCM_STATE()
    # Last received VST
    last_vst = bytes()
    last_vst_obj = {}
    
    # PDU cannot be 0 or 1
    pdu = 0x2
    # PDU is at most 4 bits
    pdu &= 0xF
    # The fragmentation header is 0b1xxxx001, where xxxx is the PDU
    frag_header = bytes([0x81 | (pdu << 3)])
    
    c_callback = BCM_CB_HANDLER(bcm_callback)
    c_alarm = BCM_ALARM_HANDLER(bcm_alarm)
    
    gea_dll_wrapper_logger.debug("Initializing GEA BCM...")
    
    # The user registration number is not used internally by the BCM DLL
    # It is thus free for use in our application
    user_registration = 7
    user_params = None

    # gea_dll_wrapper_logger.debug(f"Current beacon manager settings in moment of initialization: {json.dumps(beacon_manager_settings, indent=2)}")
    pertel_beacon_settings = beacon_manager_settings[chosen_beacon_name]
    gea_dll_wrapper_logger.info(f"Current beacon manager config: {pertel_beacon_settings}")

    send_event_polling_OK = pertel_beacon_settings['send_OK_state_alarms']
    beacon_alarm_state_polling_ms = pertel_beacon_settings['beacon_alarm_state_polling_ms']

    if pertel_beacon_settings['chosen_communication_mode'] == "serial":
        if serial_port is None:
            serial_port = pertel_beacon_settings["serial_config"]["beacon_serial_port"]
        baud_rate = pertel_beacon_settings["serial_config"]["baud_rate"]
        gea_dll_wrapper_logger.info(f"Beacon serial port: {serial_port}")

        default_baud_rate = 115200
        if baud_rate not in available_baud_rate_enum_vals:
            gea_dll_wrapper_logger.error(f"Invalid Baud Rate!!! Setting it to a default value, {default_baud_rate}")
            baud_rate_index = default_baud_rate
        gea_dll_wrapper_logger.info(f"Beacon Baud Rate: {baud_rate}")
        baud_rate_index = available_baud_rate_enum_vals[baud_rate]

        result = bcm_init_manager_fnc(
            ctypes.byref(reg_ptr),
            user_registration,
            user_params,
            serial_port,
            baud_rate_index,
            BCM_STATION_Enum.BCM_Secondary,
            beacon_alarm_state_polling_ms,
            send_event_polling_OK,
            c_callback,
            c_alarm
        )
    else:
        beacon_ip_address_bytes = pertel_beacon_settings["tcp_ip_config"]["ip_address"].encode('utf-8')
        beacon_tcp_port = pertel_beacon_settings["tcp_ip_config"]["tcp_port"]

        result = bcm_init_manager_fnc_ip(
            ctypes.byref(reg_ptr),
            user_registration,
            user_params,
            beacon_ip_address_bytes,
            beacon_tcp_port,
            BCM_STATION_Enum.BCM_Secondary,
            beacon_alarm_state_polling_ms,
            send_event_polling_OK,
            c_callback,
            c_alarm
        )

    bcm_error_wrapper(result)
    handle_init_errors()
    display_beacon_info()

def start_bst_wrapper(t_apdu_bst_datagram:bytes):
    global reg_ptr
    global chosen_beacon_name
    global frag_header

    fragmented_t_apdu_bst_datagram = frag_header + t_apdu_bst_datagram
    if len(fragmented_t_apdu_bst_datagram) > BCM_SIZEMAX_Enum.BCM_SIZEMAX_BST:
        gea_dll_loader_logger.error(f"Datagram is too big! Will probably cause a BST error")

    bst_datagram_buffer = ctypes.create_string_buffer(fragmented_t_apdu_bst_datagram, size=len(fragmented_t_apdu_bst_datagram))
    # Pointer to the buffered BST datagram
    lp_bst_datagram = ctypes.cast(bst_datagram_buffer, POINTER(BYTE))
    gea_dll_wrapper_logger.info(f"Fragmented T-APDU with BST to be sent (UPER hex): {fragmented_t_apdu_bst_datagram.hex().upper()}")

    if beacon_manager_settings[chosen_beacon_name]['change_beacon_id_internally_periodically']:
        bst_type = BCM_BST_TYPE_Enum.BCM_BST_ChangeBID
    else:
        bst_type = BCM_BST_TYPE_Enum.BCM_BST_Normal
    byte_bst_type = BYTE(bst_type)

    result = bcm_start_bst(reg_ptr,
                            lp_bst_datagram,
                            DWORD(len(fragmented_t_apdu_bst_datagram)),
                            byte_bst_type)
    bcm_error_wrapper(result)
    gea_dll_wrapper_logger.debug("No errors occurred: BST started!")
    return result

# Wait for the application to be notified through a callback
def wait_for_vst_event():
    while not callback_received_event.wait(2):
        gea_dll_wrapper_logger.debug("Waiting for callback notification...")
        pass
    gea_dll_wrapper_logger.debug("No longer waiting for VST!")

# Wait for a notification then get the VST
def wait_and_get_vst():
    wait_for_vst_event()
    return get_vst()

def get_vst():
    """
    Get the VST
    This function should only be called inside the callback
    function passed declared to the BCM Init Manager
    """
    global reg_ptr

    gea_dll_wrapper_logger.debug("Getting VST...")
    
    dword_max_size = DWORD(BCM_SIZEMAX_Enum.BCM_SIZEMAX_ANSWER)
    vst_answer_buffer_array = ctypes.create_string_buffer(BCM_SIZEMAX_Enum.BCM_SIZEMAX_ANSWER)
    vst_answer_size = DWORD()

    # Pointer where the VST datagram answer will be stored by BCM
    lp_vst_response_datagram = ctypes.cast(vst_answer_buffer_array, POINTER(BYTE))
    
    result = bcm_get_vst(reg_ptr,
                            lp_vst_response_datagram,
                            ctypes.byref(vst_answer_size),
                            dword_max_size
                            )
    
    gea_dll_wrapper_logger.debug("Handling errors (if any)...")
    bcm_error_wrapper(result)
    gea_dll_wrapper_logger.debug("VST received!")
    gea_dll_wrapper_logger.debug("Unsetting the VST received event...")
    callback_received_event.clear()

    # Slicing a ctypes array or pointer will automatically produce a Python list
    # We slice it at the given size, not the buffer's maximum size
    received_vst_list = lp_vst_response_datagram[:vst_answer_size.value]

    # Converting VST to bytes structure and storing it in last_vst attribute
    t_apdu_containing_vst = bytes(received_vst_list)

    # Log the VST
    gea_dll_wrapper_logger.info(f"Received VST value (UPER hex): {t_apdu_containing_vst.hex().upper()}")
    return t_apdu_containing_vst

def send_req_t_apdu_and_receive_resp_t_apdu(t_apdu_datagram: bytes, close_transaction_transaction=False):
    global frag_header

    fragmented_t_apdu_datagram = frag_header + t_apdu_datagram
    lp_cmd_datagram = ctypes.cast(fragmented_t_apdu_datagram, POINTER(BYTE))
    
    # Buffers and pointers for command response datagrams
    cmd_response_buffer_array = ctypes.create_string_buffer(BCM_SIZEMAX_Enum.BCM_SIZEMAX_CMD)
    dword_cmd_resonse_max_size = DWORD(BCM_SIZEMAX_Enum.BCM_SIZEMAX_CMD)
    lp_cmd_response_datagram = ctypes.cast(cmd_response_buffer_array, POINTER(BYTE))
    cmd_response_size = DWORD()

    gea_dll_wrapper_logger.debug(f"Command to be sent value (UPER hex): {fragmented_t_apdu_datagram.hex().upper()}")

    result = bcm_send_cmd(
        reg_ptr,
        lp_cmd_datagram,
        DWORD(len(fragmented_t_apdu_datagram)),
        lp_cmd_response_datagram,
        ctypes.byref(cmd_response_size),
        dword_cmd_resonse_max_size,
        close_transaction_transaction
        )
    bcm_error_wrapper(result)

    # Iterating cmd response pointer to get its value/contents
    response_as_list = lp_cmd_response_datagram[:cmd_response_size.value]
    return bytes(response_as_list)


def bcm_callback(reg_ptr_param, callback_type, error_code):
    """
    This is the default Callback function.

    As callback functions are directly called by the internal thread which is
    managing the communication with the beacon they should return as
    quickly as possible
    """
    global external_callback

    gea_dll_wrapper_logger.debug("CB: Callback notification received!")
    if callable(external_callback):
        gea_dll_wrapper_logger.debug("CB: External callback function present! (from the frontend, for exemple)")
        gea_dll_wrapper_logger.debug("CB: We now call/notify it!")
        external_callback(callback_type, error_code)

    try:
        cb_error_handler(callback_type, error_code)
        bcm_error_wrapper(error_code)
        gea_dll_wrapper_logger.debug("CB: OK! No error occurred in callback: This means a VST was received!")
        gea_dll_wrapper_logger.debug("CB: We thus notify all threads waiting on the callback_received_notifier condition")
        callback_received_event.set()
    except Layer7Exception:
        gea_dll_wrapper_logger.error(f"CB: Error, with BCM error code {error_code}")
def bcm_alarm(reg_ptr_param, alarm_type, alarm_state):
    """
    This is the default Alarm function (it is a callback function)
    
    Differently from the other callback function, 'alarm' has a state/flag.
    The state of the alarm is True until it disappears.
    This is useful to display the beacon's state (according to its L7 interface).
    """
    global external_alarm

    gea_dll_wrapper_logger.debug(f"AL: Alarm notification ({alarm_type}) received!")
    if callable(external_alarm):
        gea_dll_wrapper_logger.debug("AL: External alarm function present! (from the frontend, for exemple)")
        gea_dll_wrapper_logger.debug("AL: We now call/notify it!")
        external_alarm(alarm_type, alarm_state)

    if alarm_type == BCM_ALARMS_Enum.BCM_AlarmPeriph or alarm_type == BCM_ALARMS_Enum.BCM_AlarmBeacon:
        gea_dll_wrapper_logger.error(f"Error in Alarm! Description: {BCM_Alarm.get_description(alarm_type)}") 
    gea_dll_wrapper_logger.debug(f"Alarm description: {BCM_Alarm.get_description(alarm_type)}")
    
    if alarm_type == BCM_ALARMS_Enum.BCM_EventPollingOK:
        beacon_state_ok_event.set()
    return
def handle_init_errors():
    """This function handles initialization issues if there are any, like:
        Unclosed transactions
        Beacon not in stopped mode
        etc."""
    global beacon_state

    gea_dll_wrapper_logger.info("Handling initialization issues (if there are any)...")
    gea_dll_wrapper_logger.debug("Trying to get the latest beacon state...")
    result = update_state()

    gea_dll_wrapper_logger.debug(f"Beacon state iterator keys: {list(iter(beacon_state))}")
    gea_dll_wrapper_logger.debug(beacon_state)

    if result == BCM_ERR_Enum.BCM_NoError:
        pass
    elif result == BCM_ERR_Enum.BCM_SocketNotConnected:
        gea_dll_wrapper_logger.error("Wait for socket to connect before sending commands!")
    else:
        gea_dll_wrapper_logger.critical("We could not handle the error, so it will be raised")
        bcm_error_wrapper(result)
    
    wait_for_ok_alarm()

    gea_dll_wrapper_logger.debug("Updating beacon state (It should now be OK)...")
    result = update_state()

    # If a previous transaction was not closed, we forcefully reset the beacon
    if beacon_state.trxInProgress:
        gea_dll_wrapper_logger.error("Previously unclosed transaction in progress!")
        gea_dll_wrapper_logger.info("We will forcefully reset the beacon...")
        reset_beacon()
        
        wait_for_ok_alarm()

    if beacon_state.mode == BCM_MODE_Enum.BCM_MOD_Stopped:
        change_trx_mode(BCM_MODE_Enum.BCM_MOD_Transparent)
        gea_dll_wrapper_logger.debug("Changed operating mode to transparent!")

    gea_dll_wrapper_logger.debug("Waiting 1 second and then updating the beacon's state...")
    time.sleep(1)
    update_state()
    return beacon_state

def wait_for_ok_alarm():
    global beacon_state
    global chosen_beacon_name

    beacon_config = beacon_manager_settings[chosen_beacon_name]
    if beacon_config['send_OK_state_alarms'] == True and beacon_config['beacon_alarm_state_polling_ms'] > 0:
        gea_dll_wrapper_logger.debug("Waiting for an OK state alarm...")
        beacon_state_ok_event.wait()
        gea_dll_wrapper_logger.debug("Beacon is OK!!!")
    else:
        gea_dll_wrapper_logger.debug("Skipping wait for OK state alarm: OK state is not being sent/alarmed")

def display_cb_event_trigger():
    gea_dll_wrapper_logger.debug("\tWaiting for CB notification...")
    callback_received_event.wait()
    gea_dll_wrapper_logger.debug("\tCB notification received!!! You can receive a VST now.")

def update_beacon_id() -> bytes:
    """
    This is a specific function for TGBV hardware since managing the BeaconId is not straightforward and maybe even buggy with it.
    There seems to be a bug for GEA_CATL_TGB_V1_3#.
    Not a bug in GEA_TGB_VOIE_V1.5# and TGB_VOIE#1.8.0#, though.
    """
    global reg_ptr
    global last_beacon_id
    
    gea_dll_wrapper_logger.debug("Getting Beacon ID...")
    
    beacon_id_buffer_array = ctypes.create_string_buffer(BCM_FIXED_SIZES_Enum.BCM_SIZE_BEACONID)

    # Pointer where the BeaconID will be stored by BCM
    lp_beacon_id = ctypes.cast(beacon_id_buffer_array, POINTER(BYTE))

    result = bcm_get_beacon_id(reg_ptr, lp_beacon_id)
    last_beacon_id = bytes(beacon_id_buffer_array[0:BCM_FIXED_SIZES_Enum.BCM_SIZE_BEACONID])

    gea_dll_wrapper_logger.debug(f"Latest Beacon ID in hex: {last_beacon_id.hex().upper()}")
    return result

def update_state() -> ST_BCM_STATE:
    global reg_ptr
    global beacon_state

    gea_dll_wrapper_logger.debug(f"Updating beacon state...")
    if beacon_state.trxInProgress:
        gea_dll_wrapper_logger.error(f"Do not try to update the state: A transaction is in progress! Otherwise, an Exception will be raised.")
    
    result = bcm_check_state(reg_ptr, ctypes.byref(beacon_state))
    bcm_error_wrapper(result)

    gea_dll_wrapper_logger.debug(f"Beacon state: {beacon_state}")
    gea_dll_wrapper_logger.info(f"Beacon state description: {beacon_state.get_description()}")
    return result

def is_mode(mode_code: int):
    global beacon_state
    if beacon_state.mode == mode_code:
        return True

def check_if_transaction_in_progress():
    global beacon_state
    return beacon_state.trxInProgress

def get_last_beacon_state_dict():
    global beacon_state

    gea_dll_wrapper_logger.debug(f"Beacon state dict: {dict(beacon_state)}")
    return dict(beacon_state)
def get_last_beacon_state_description():
    global beacon_state

    gea_dll_wrapper_logger.debug(f"Beacon state description: {beacon_state.get_description()}")
    return beacon_state.get_description()

def display_beacon_info():
    """This function can only be called AFTER INITIALIZATION.
    That is, reg_ptr must point to a initialized BCM structure"""
    gea_dll_wrapper_logger.debug("Getting beacon configuration via DLL...")
    bcm_config = get_config()
    gea_dll_wrapper_logger.debug(f"Displaying config data...: {bcm_config}")

    change_trx_mode(BCM_MODE_Enum.BCM_MOD_Transparent)
    gea_dll_wrapper_logger.debug("Changed mode to transparent!")

    gea_dll_wrapper_logger.debug("Getting beacon state...")
    result = update_state()

def get_beacon_id():
    global last_beacon_id

    if not "last_beacon_id" in globals():
        update_beacon_id()

    return last_beacon_id

def get_config():
    """This function can only be called AFTER INITIALIZATION.
    That is, reg_ptr must point to a initialized BCM structure"""
    global reg_ptr

    bcm_config = ST_BCM_CONFIG()
    try:
        result = bcm_get_config(reg_ptr, ctypes.byref(bcm_config))
        bcm_error_wrapper(result)
    except Layer7Exception:
        gea_dll_wrapper_logger.error("This function can only be called AFTER INITIALIZATION!!")

    return bcm_config

def change_trx_mode(operating_mode_code):
    global reg_ptr

    gea_dll_wrapper_logger.debug(f"[TGBV L7]: Changing mode to ({operating_mode_code})")
    result = bcm_change_mode(reg_ptr, operating_mode_code)
    bcm_error_wrapper(result)
    gea_dll_wrapper_logger.debug(f"[TGBV L7]: Finished changing mode")
def shutdown():
    global reg_ptr

    gea_dll_wrapper_logger.debug(f"Shutting down GEA TGBV beacon...")
    result = bcm_close_manager(ctypes.byref(reg_ptr))
    bcm_error_wrapper(result)
    gea_dll_wrapper_logger.debug(f"Shut down successfully!!")
    
def reset_beacon():
    global reg_ptr

    result = bcm_reset(reg_ptr)
    bcm_error_wrapper(result)

def set_mmi(close = False):
    """
    Simple SetMMI request.
    This is used by the Layer 7 wrapper to close transactions.
    This is probably useless in the Layer 7 application (We can just reset/stop the beacon).
    """
    global frag_header

    # SetMMI ActionType is 0xA, or 10 in decimal
    set_mmi_request = [frag_header, 0x05, 0x00, 0x0A, 0x00, 0x00]
    set_mmi_datagram = bytes(set_mmi_request)
    send_req_t_apdu_and_receive_resp_t_apdu(set_mmi_datagram, close)
def send_close_transaction_to_obu():
    """
    To close the transaction, we just send a SetMMI request...
    """
    command_response = set_mmi(True)
    return command_response
def close():
    global beacon_state

    gea_dll_wrapper_logger.info(f"Stopping Beacon Manager!")
    # If a transaction is still open, we close it
    if beacon_state.trxInProgress:
        # We probably don't need to close the transaction, this is an unnecessary step/precaution
        gea_dll_wrapper_logger.info(f"A transaction was in progress according to the DLL! Closing it...")
        send_close_transaction_to_obu()
    
    update_state()

    if beacon_state.mode != BCM_MODE_Enum.BCM_MOD_Stopped:
        change_trx_mode(BCM_MODE_Enum.BCM_MOD_Stopped)
        gea_dll_wrapper_logger.debug("Changed mode to stopped!")