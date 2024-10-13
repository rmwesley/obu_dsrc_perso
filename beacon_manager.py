from ASN.compiled_DSRC_instances import CCCv4_1 as CCC2019
from ASN.compiled_DSRC_instances import EFCv10_1 as EFC
from ASN.compiled_DSRC_instances import LACv2_1

from datetime import datetime
import logging

from gea_bcm_dll_wrapper import BCM_GEA_DLL_Wrapper

bcm_logger = logging.getLogger(__name__)

# Defining the BeaconManager class
class BeaconManager:
    def __init__(self):
        chosen_beacon_name = beacon_manager_settings["chosen_beacon_name"]
        self.switch_beacon(chosen_beacon_name)
    def switch_beacon(self, chosen_beacon_name):
        if chosen_beacon_name == "TGBV":
            self.beacon_l7_wrapper.close()
            self.beacon_l7_wrapper = BCM_GEA_DLL_Wrapper()
    def update_beacon_id(self) -> EFC.EfcDsrcGeneric.BeaconID:
        """
        This is a specific function for TGBV hardware since managing the BeaconId is not straightforward and maybe even buggy with it.
        There seems to be a bug for GEA_CATL_TGB_V1_3#.
        Not a bug in GEA_TGB_VOIE_V1.5# and TGB_VOIE#1.8.0#, though.
        """
        bcm_logger.debug("Getting Beacon ID...")
        
        beacon_id_buffer_array = ctypes.create_string_buffer(BCM_FIXED_SIZES_Enum.BCM_SIZE_BEACONID)

        # Pointer where the BeaconID will be stored by BCM
        lp_beacon_id = ctypes.cast(beacon_id_buffer_array, POINTER(BYTE))

        bcm_get_beacon_id(self.reg_ptr, lp_beacon_id)
        self.last_beacon_id = bytes(beacon_id_buffer_array[0:BCM_FIXED_SIZES_Enum.BCM_SIZE_BEACONID])

        bcm_logger.debug(f"Latest Beacon ID in hex: {self.last_beacon_id.hex().upper()}")
        return self.last_beacon_id
    # Start sending a BST
    def start_bst(self, manufacturer_id=0x31, individual_id=0x111, mandapplications=[1, 20, 29], profile=0x00, profile_list=[0x00], non_mand_applications = [], bst_type:int = BCM_BST_TYPE_Enum.BCM_BST_ChangeBID):
        mandApplications = [{'aid': mandatory_aid} for mandatory_aid in mandapplications]

        bst_value = {
            'rsu': {
                'manufacturerid': manufacturer_id,
                'individualid': individual_id
                },
            'time': datetime.utcnow().timestamp(),
            'profile': profile,
            'mandApplications': mandApplications,
            'profileList': profile_list
            }
        EFC.EfcDsrcGeneric.BST.set_val(bst_value)
        self.last_sent_bst = EFC.EfcDsrcGeneric.BST.to_uper()
        bcm_logger.debug(f"BST in UPER encoding in hex: {self.last_sent_bst.hex().upper()}")

        EFC.EfcDsrcGeneric.T_APDUs.set_val(('initialisation-request', EFC.EfcDsrcGeneric.BST._val))
        bcm_logger.debug(f"T_APDU containing BST in JER: {EFC.EfcDsrcGeneric.T_APDUs.to_jer()}")

        self.last_sent_fragmented_t_apdu_containing_bst = self.frag_header + EFC.EfcDsrcGeneric.T_APDUs.to_uper()
        bcm_logger.debug(f"Fragmented T_APDU containing BST: {self.last_sent_fragmented_t_apdu_containing_bst.hex().upper()}")

        if len(self.last_sent_bst) > BCM_SIZEMAX_Enum.BCM_SIZEMAX_BST:
            bcm_logger.error(f"Datagram is too big! Will probably cause a BST error")
        result = self.start_bst_wrapper(self.last_sent_fragmented_t_apdu_containing_bst, bst_type)

        bcm_logger.debug("We now get the lastest BeaconID just after starting the BST")
        self.update_beacon_id()
        bcm_logger.debug(f"Last BeaconID: {self.last_beacon_id.hex().upper()}")

        return result
    
    def initialize_transaction(self, manufacturer_id=0x31, individual_id=0x111, mandapplications=[1, 20, 29], profile=0x00, profile_list=[0x00], non_mand_applications = [], bst_type:int = BCM_BST_TYPE_Enum.BCM_BST_ChangeBID):
        """
        The initialization phase comprises 2 steps for the beacon:
        Start of a BST, and
        wait for a VST

        The initialization phase locks the transaction thread when a VST is received!
        When the transaction is closed (no longer in progress) the transaction lock is released.
        """
        if self.beacon_state.trxInProgress:
            bcm_logger.error("Do not try to initilize a transaction! One is already in progress!")
            return
        bcm_logger.debug("We lock the thread until the opened transaction is closed!")

        self.start_bst(manufacturer_id, individual_id, mandapplications, profile, profile_list, non_mand_applications, bst_type)
        bcm_logger.debug("No errors occurred when starting BST!")
        
        bcm_logger.info("We now wait on the main thread until we a VST notification is received...")
        self.wait_for_vst_notification()
        #self.no_transaction_in_progress.set()

        bcm_logger.info("A VST notification was received! We now get the VST")
        fragmented_t_apdu_init_resp_datagram = self.beacon_l7_wrapper.get_vst()
        bcm_logger.info(f"Fragmented T_APDU containing VST: {fragmented_t_apdu_init_resp_datagram.hex().upper()}")
        
        bcm_logger.debug("We now remove the fragmentation header and instantiate an T_APDU object from the response!")
        t_apdu_init_resp_datagram = bytes(fragmented_t_apdu_init_resp_datagram[1:])
        EFC.EfcDsrcGeneric.T_APDUs.from_uper(t_apdu_init_resp_datagram)
        bcm_logger.debug(f"T-APDU without fragmentation header: {t_apdu_init_resp_datagram}")
        
        bcm_logger.debug("We now instantiate a T_APDU object from the response!")
        bcm_logger.info(f"T_APDU containing VST in JER: {EFC.EfcDsrcGeneric.T_APDUs.to_jer()}")
        bcm_logger.debug(f"Instantiated T_APDU object value: {EFC.EfcDsrcGeneric.T_APDUs._val}")
        bcm_logger.info(f"Instantiated T_APDU in JER: {EFC.EfcDsrcGeneric.T_APDUs.to_jer()}")

        # Decoding VST
        bcm_logger.debug("We now obtain the VST object from the T_APDU response!")
        bcm_logger.debug("VST is a parameterized type, so we cannot decode/encode it, only the APDU!")
        self.last_received_vst = EFC.EfcDsrcGeneric.T_APDUs._to_jval()["initialisation-response"]

        bcm_logger.debug(f'Decoded VST: {self.last_received_vst}')
        return self.last_received_vst

    def send_command(self):
        self.last_cmd_response = self.beacon_l7_wrapper.send_command(datagram=)
        bcm_logger.debug(f"Command response in hex format: {self.last_cmd_response.hex().upper()}")
        return self.last_cmd_response
    
    def send_req_t_apdu_and_obtain_resp_t_apdu(self, asn1_request_t_apdu_value, close=False) -> dict:
        bcm_logger.debug(f"Preparing request T_APDU to be sent...")
        EFC.EfcDsrcGeneric.T_APDUs.set_val(asn1_request_t_apdu_value)
        bcm_logger.debug(f"Request T_APDU value: {EFC.EfcDsrcGeneric.T_APDUs._val}")
        bcm_logger.debug(f"T_APDU in JER: {EFC.EfcDsrcGeneric.T_APDUs.to_jer()}")
        fragmented_t_apdu = self.frag_header + EFC.EfcDsrcGeneric.T_APDUs.to_uper()

        bcm_logger.info(f"Sending fragmented T_APDU: {fragmented_t_apdu.hex().upper()}")
        fragmented_t_apdu_with_get_response_bytes = self.send_command(fragmented_t_apdu, close)
        bcm_logger.debug(f"Decoding received response T_APDU...")
        bcm_logger.info(f"Fragmented T_APDU response obtained from beacon in hex (supposed to be UPER): {fragmented_t_apdu_with_get_response_bytes.hex().upper()}")
        t_apdu_with_get_response_bytes = bytes(fragmented_t_apdu_with_get_response_bytes[1:])

        EFC.EfcDsrcGeneric.T_APDUs.from_uper(t_apdu_with_get_response_bytes)
        bcm_logger.debug(f"Response T_APDU value: {EFC.EfcDsrcGeneric.T_APDUs._val}")
        bcm_logger.debug(f"Response T_APDU decoded with JER: {EFC.EfcDsrcGeneric.T_APDUs.to_jer()}")
        json_encoded_response_t_apdu = EFC.EfcDsrcGeneric.T_APDUs._to_jval()
        bcm_logger.debug(f"Response T_APDU in JSON value: {json_encoded_response_t_apdu}")
        
        bcm_logger.info(f"Checking if T-APDU contains a return (ret) value (error code)...")
        try:
            return_code = json_encoded_response_t_apdu["ret"]
            if return_code == 0:
                bcm_logger.info(f"Return code is present and is 0! (No errors)")
            else:
                bcm_logger.error(f"Error code present! Return Code: {return_code}") 
        except KeyError:
            bcm_logger.info(f"No return code in T-APDU! (No errors)")
        return json_encoded_response_t_apdu

    def get_eid_info_from_last_vst(self, eid:int) -> int:
        vst_application_index = -1
        bcm_logger.debug(f"Getting application with EID {eid}")
        for index, application in enumerate(self.last_received_vst['applications']):
            bcm_logger.debug(f"Application details: {application}")
            if application["eid"] == eid:
                vst_application_index = index
        if vst_application_index == -1:
            bcm_logger.info(f"EID {eid} is not present!")
        else:
            bcm_logger.debug(f"Index of EID {eid} on VST is {vst_application_index}")
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
        # That is, remove optional elements that map to None
        # This is specially the case for the optional accessCredentials
        get_req_value = {key: value for key, value in get_req_value.items() if value is not None}

        EFC.EfcDsrcGeneric.Get_Request.set_val(get_req_value)
        bcm_logger.debug(f"Get.Request value: {EFC.EfcDsrcGeneric.Get_Request._val}")
        bcm_logger.info(f"Get.Request in JER: {EFC.EfcDsrcGeneric.Get_Request.to_jer()}")

        t_apdu_with_get_request_value = ('get-request', get_req_value)
        json_encoded_response_t_apdu = self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_get_request_value)

        bcm_logger.debug("We now obtain the GET.response object from the T_APDU response!")
        bcm_logger.debug("GET.response is a parameterized type, so we cannot encode/decode it, only the T_APDU!")
        
        return json_encoded_response_t_apdu

    def send_action_request(self,
            mode=True,
            eid=0,
            actionType=0xA,
            accessCredentials = None,
            actionParameter = None,
            iid = None,
            close = False):
        if not actionParameter:
            actionParameter = ('setmmirq', 0)
        bcm_logger.debug(f"Preparing an ACTION.request...")
        bcm_logger.debug(f"ActionType value is {actionParameter[0]}")

        # ACTION.request has a parameter, which needs to be inside a container
        EFC.EfcDsrcGeneric.EfcContainer.set_val(actionParameter)
        parameter_tag = EFC.EfcDsrcGeneric.EfcContainer.TAG

        bcm_logger.debug(f"ActionParameter is an EfcContainer of Type {actionParameter[0]} (tag {parameter_tag}) value decoded with JER: {EFC.EfcDsrcGeneric.EfcContainer.to_jer()}")
        bcm_logger.debug(f"ActionParameter is an EfcContainer of Type {actionParameter[0]} (tag {parameter_tag}) value decoded with PER: {EFC.EfcDsrcGeneric.EfcContainer.to_uper()}")
        
        t_apdu_with_action_req_value = ('action-request', {
            'mode': mode,
            'eid': eid,
            'actionType': actionType,
            'accessCredentials': accessCredentials,
            'actionParameter': actionParameter,
            'iid': iid
            })
        # Ignore keys in dict that map to None!!
        # That is, remove optional elements that map to None
        # This is specially the case for the optional accessCredentials and iid
        t_apdu_with_action_req_value = {key: value for key, value in t_apdu_with_action_req_value.items() if value is not None}

        EFC.EfcDsrcGeneric.T_APDUs.set_val(t_apdu_with_action_req_value)
        bcm_logger.info(f"ACTION.request with ActionType {actionType} and actionParameter of type {actionParameter[0]} being now sent...")

        json_encoded_response_t_apdu = self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_set_mmi_action_req_value, close)
        return json_encoded_response_t_apdu

    def presentation_request(self,
            eid:int,
            accessCredentials:int,
            attrIdList=[],
            operator_auk_ref=111,
            response_expected=True,
            close=False):
        return self.send_get_stamped_request(eid, accessCredentials, attrIdList, operator_auk_ref, response_expected, close)
    def send_get_stamped_request(self,
            eid:int,
            accessCredentials:int,
            attrIdList=[],
            operator_auk_ref=111,
            response_expected=True,
            close=False):
        actionParameter = self.get_stamped_request_action_parameter_preparation(eid, accessCredentials, attrIdList, operator_auk_ref, response_expected, close)

        bcm_logger.debug("Sending a GET_STAMPED.request (Presentation request)...")
        t_apdu_with_get_request_value = ('get-request', get_req_value)
        json_encoded_response_t_apdu = self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_get_request_value)

        bcm_logger.debug("We now obtain the GET_STAMPED.response object from the T_APDU response!")
        bcm_logger.debug("GET_STAMPED.response is a parameterized type, so we cannot encode/decode it, only the T_APDU!")
        
        # ActionType is 0 for GET_STAMPED.request and Mode is True (Always expects a response)
        json_encoded_response_t_apdu = self.send_action_request(True, eid, 0, accessCredentials, actionParameter, close)

        bcm_logger.debug("We now obtain the GET_STAMPED.request object from the T_APDU response!")
        bcm_logger.debug("GET_STAMPED.request is a parameterized type, so we cannot encode/decode it, only the T_APDU!")
        try:
            bcm_logger.debug(f"GET_STAMPED.response (Presentation response): {json_encoded_response_t_apdu['action-response']['responseParameter']}")
        except KeyError:
            bcm_logger.error(f"Reponse Parameter not present in GET_STAMPED.reponse!")
        return json_encoded_response_t_apdu
    
    def get_stamped_request_action_parameter_preparation(self,
            eid:int,
            accessCredentials:int,
            attrIdList=[],
            operator_auk_ref=111):
        """
        ACTION.request of type GET_STAMPED.request (ActionType=0).

        The ActionParameter is thus of type GetStampedRs
        """
        if not attrIdList:
            attrIdList = []

        bcm_logger.debug(f"Preparing a GET_STAMPED.request to get attributes with ids {attrIdList}")
        bcm_logger.debug(f"Computing RndRSE value...")

        rnd_rse = EFC.EfcDataDictionary.DateAndTime.set_val({ 
            'timeDate':{
                'year': datetime.utcnow().year,
                'month': datetime.utcnow().month,
                'day': datetime.utcnow().day,
            },
            'timeCompact':{
                'hours': datetime.utcnow().hour,
                'mins': datetime.utcnow().minute,
                'doubleSecs': datetime.utcnow().second // 2
            }
        })
        bcm_logger.debug(f"RndRSE or SessionTime value (of type DateAndTime) in JER: {EFC.EfcDataDictionary.DateAndTime.to_jer()}")

        get_stamped_req_value = {
            'attributeIdList': attrIdList,
            'nonce': rnd_rse,
            'keyRef': operator_auk_ref
            }
        EFC.EfcDsrcApplication.GetStampedRs.set_val(get_stamped_req_value)
        
        bcm_logger.debug(f"GetStampedRs value: {EFC.EfcDsrcGeneric.Get_Request._val}")
        bcm_logger.info(f"GetStampedRs in JER: {EFC.EfcDsrcGeneric.Get_Request.to_jer()}")
        return get_stamped_req_value

    def set_mmi(self, eid=0, close=False):
        bcm_logger.debug(f"Preparing a SET_MMI.request")
        bcm_logger.debug(f"The function to send ACTION.requests is defined to send a SET_MMI by default if no arguments are provided!")

        # SetMMI is a parameterized type, so it needs to be inside a container
        set_mmi_efc_container_value = ('setmmirq', set_mmi_request_value)
        EFC.EfcDsrcGeneric.EfcContainer.set_val(set_mmi_efc_container_value)
        bcm_logger.debug(f"EfcContainer of Type 69 (SET_MMI) value decoded with JER: {EFC.EfcDsrcGeneric.EfcContainer.to_jer()}")
        bcm_logger.debug(f"EfcContainer of Type 69 (SET_MMI) value decoded with PER: {EFC.EfcDsrcGeneric.EfcContainer.to_uper()}")
        
        # SetMMI ActionType is 0xA, or 10 in decimal
        set_mmi_action_request_val = {
            'mode': True,
            'eid': eid,
            'actionType': 0xA,
            'actionParameter': set_mmi_efc_container_value
            }
        
        t_apdu_with_set_mmi_action_req_value = ('action-request', set_mmi_action_request_val)
        bcm_logger.info(f"ACTION.request of Type 10 (SET_MMI) being now sent...")

        t_apdu_with_action_response = self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_set_mmi_action_req_value, close)
        return t_apdu_with_action_response