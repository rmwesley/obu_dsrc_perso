import ctypes
from ctypes import POINTER, wintypes, c_char_p, c_uint, c_int, c_byte, c_bool, c_ulong, c_ushort
from ctypes.wintypes import HWND, LPCWSTR, UINT, BYTE, WORD, DWORD, CHAR, BOOL, LPVOID

import logging
dll_loader_logger = logging.getLogger(__name__)

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
        return BCMError.errors.get(error_code, "Unknown error")

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
    def __repr__(self):
        str_state = f"<ST_BCM_STATE:\n"
            
        for field_name, field_type in self._fields_:
            str_state += f"  {field_name}: {getattr(self, field_name)}\n"
        str_state += f">"
        
        return str_state
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
dll_loader_logger.debug("Loading BeaconManager.dll...")
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
                                           POINTER(ST_BCM_REG_PTR),
                                           POINTER(BYTE))
BCM_LPFN_GetATLIO = ctypes.WINFUNCTYPE(BCM_ERR,
                                        POINTER(ST_BCM_REG_PTR),
                                        POINTER(DWORD))

# Get the addresses of the long pointers to the foreign functions, LPFNs
dll_loader_logger.debug("Getting the pointers to the addresses of the DLL's foreign functions...")

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
dll_loader_logger.debug("Instantiating the ctypes function prototypes (to get Python callables)...")

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

dll_loader_logger.info("Getting the DLL version...")

bytes_dll_version = get_lib_version().to_bytes(4, 'big')
dll_loader_logger.debug(bytes_dll_version)

dll_loader_logger.info(f"Loaded DLL version: {bytes_dll_version[1]}.{bytes_dll_version[2]}.{bytes_dll_version[3]}")