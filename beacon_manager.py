# from ASN.compiled_DSRC_instances import CCCv4_1 as EFC_CCC_LAC_asn1_objs
# from ASN.compiled_DSRC_instances import EFCv10_1 as EFC_CCC_LAC_asn1_objs
from ASN.compiled_DSRC_instances import LACv2_1 as EFC_CCC_LAC_asn1_objs

from datetime import datetime
import json
import logging
import threading

from gea_bcm_dll_wrapper import BCM_GEA_DLL_Wrapper, BCM_BST_TYPE_Enum, BCM_MODE_Enum
import custom_its_per_decoders
import dsrc_security

bcm_logger = logging.getLogger(__name__)

with open('settings/beacon_manager_config.json', 'r') as beacon_manager_settings_file:
    beacon_manager_settings = json.load(beacon_manager_settings_file)

class BeaconManagerException(Exception):
    pass
class TransactionException(Exception):
    pass

# Defining the BeaconManager class
class BeaconManager:
    def __init__(self, aid=1):
        default_beacon_name = beacon_manager_settings["default_beacon_name"]
        self.l7_initialization_phase_lock = threading.Lock()
        self.l7_transfer_kernel_lock = threading.Lock()
        self.safe_switch_beacon(chosen_beacon_name = default_beacon_name)

        # if aid == 1:
        #     self.TApdu_container = self.TApdu_container
        self.TApdu_container = EFC_CCC_LAC_asn1_objs.EfcCcc.CccTApdus
    def safe_switch_beacon(self, chosen_beacon_name):
        if hasattr(self, 'beacon_l7_wrapper'):
            self.beacon_l7_wrapper.close()
        if chosen_beacon_name == "TGBV":
            self.beacon_l7_wrapper = BCM_GEA_DLL_Wrapper()
            self.chosen_beacon_name = "TGBV"
    # Start sending a BST
    def start_bst(self, manufacturer_id=0x31, individual_id=0x111, mand_applications=[1, 20, 29], profile=0x00, profile_list=[0x00], non_mand_applications = [], bst_type:int = BCM_BST_TYPE_Enum.BCM_BST_ChangeBID):
        mand_applications = [{'aid': mandatory_aid} for mandatory_aid in mand_applications]

        bst_value = {
            'rsu': {
                'manufacturerid': manufacturer_id,
                'individualid': individual_id
                },
            'time': int(datetime.utcnow().timestamp()),
            'profile': profile,
            'mandApplications': mand_applications,
            'profileList': profile_list
            }
        EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.BST.set_val(bst_value)
        self.last_sent_bst = EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.BST.to_uper()
        bcm_logger.debug(f"BST value (UPER hex): {self.last_sent_bst.hex().upper()}")

        self.TApdu_container.set_val(('initialisationRequest', EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.BST._val))
        bcm_logger.debug(f"T_APDU containing BST in JER: {self.TApdu_container.to_jer()}")

        self.last_sent_t_apdu_containing_bst = self.TApdu_container.to_uper()

        self.l7_transfer_kernel_lock.acquire()
        self.l7_initialization_phase_lock.acquire()
        result = self.beacon_l7_wrapper.start_bst_wrapper(self.last_sent_t_apdu_containing_bst, bst_type)

        bcm_logger.debug("We now get the lastest BeaconID just after starting the BST")
        self.beacon_l7_wrapper.update_beacon_id()
        bcm_logger.debug(f"Last BeaconID: {self.beacon_l7_wrapper.last_beacon_id.hex().upper()}")

        return result
    
    def initialize_transaction(self, manufacturer_id=0x31, individual_id=0x111, mand_applications=[1, 20, 29], profile=0x00, profile_list=[0x00], non_mand_applications = [], bst_type:int = BCM_BST_TYPE_Enum.BCM_BST_ChangeBID):
        """
        The initialization phase comprises 2 steps for the beacon:
        Start of a BST, and
        wait for a VST

        The initialization phase locks the transaction thread when a VST is received!
        When the transaction is closed (no longer in progress) the transaction lock is released.
        """
        self.beacon_l7_wrapper.update_state()
        if self.beacon_l7_wrapper.beacon_state.mode == BCM_MODE_Enum.BCM_MOD_Stopped:
            raise BeaconManagerException("Beacon is in Stopped mode, not Transparent!!") 
        if self.beacon_l7_wrapper.beacon_state.trxInProgress:
            bcm_logger.error("Do not try to initilize a transaction! One is already in progress!")
            # bcm_logger.debug("We lock the thread until the opened transaction is closed!")
            raise BeaconManagerException("Transaction already in progress!!")

        self.start_bst(manufacturer_id=manufacturer_id, individual_id=individual_id, mand_applications=mand_applications, profile=profile, profile_list=profile_list, non_mand_applications=non_mand_applications, bst_type=bst_type)
        bcm_logger.debug("No errors occurred when starting BST!")
        
        bcm_logger.info("We now wait on the main thread until we a VST notification is received...")
        self.beacon_l7_wrapper.wait_for_vst_notification()
        self.l7_initialization_phase_lock.release()
        self.l7_transfer_kernel_lock.release()
        #self.no_transaction_in_progress.set()

        bcm_logger.info("A VST notification was received! We now get the VST")
        fragmented_t_apdu_init_resp_datagram = self.beacon_l7_wrapper.get_vst()
        bcm_logger.info(f"Fragmented T_APDU containing VST (UPER hex): {fragmented_t_apdu_init_resp_datagram.hex().upper()}")
        
        bcm_logger.debug("We now remove the fragmentation header and instantiate an T_APDU object from the response!")
        t_apdu_init_resp_datagram = bytes(fragmented_t_apdu_init_resp_datagram[1:])
        self.TApdu_container.from_uper(t_apdu_init_resp_datagram)
        bcm_logger.debug(f"T-APDU without fragmentation header (UPER hex): {t_apdu_init_resp_datagram}")
        
        bcm_logger.debug("We now instantiate a T_APDU object from the response!")
        bcm_logger.debug(f"Instantiated T_APDU object ASN1 decoding/representation: {self.TApdu_container.to_asn1()}")
        bcm_logger.info(f"T_APDU containing VST in JER: {self.TApdu_container.to_jer()}")
        bcm_logger.debug(f"Instantiated T_APDU object value: {self.TApdu_container._val}")
        bcm_logger.info(f"Instantiated T_APDU in JER: {self.TApdu_container.to_jer()}")
        self.last_response_t_apdu_json = self.TApdu_container._to_jval()
        self.last_response_t_apdu_value = self.TApdu_container._val

        # Storing VST in field
        self.last_vst_json = self.last_response_t_apdu_json['initialisationResponse']
        self.last_vst_value = self.last_response_t_apdu_value[1]

        # # Decoding VST
        # bcm_logger.debug("We now obtain the VST object from the T_APDU response!")
        # bcm_logger.debug("VST is a parameterized type, so we cannot decode/encode it, only the APDU!")
        # self.last_initialisation_response_json = self.last_response_t_apdu_json['initialisationResponse']

        # bcm_logger.debug(f'Decoded VST: {self.last_initialisation_response_json}')
        # return self.last_initialisation_response_json
        return self.last_response_t_apdu_json

    def find_eid_with_accepted_contract(self):
        eid = None
        return eid
    def get_efc_cm_for_eid(self, eid):
        return self.get_parameter_bytes_from_eid_on_vst_value(eid=eid)

    def send_req_t_apdu_and_obtain_resp_t_apdu(self, asn1_request_t_apdu_value, close=False) -> dict:
        bcm_logger.debug(f"Preparing request T-APDU to be sent...")
        self.TApdu_container.set_val(asn1_request_t_apdu_value)
        bcm_logger.debug(f"Request T-APDU value: {self.TApdu_container._val}")
        bcm_logger.debug(f"T-APDU in JER: {self.TApdu_container.to_jer()}")

        # Sending command!!!
        self.l7_transfer_kernel_lock.acquire()
        fragmented_t_apdu_with_get_response_bytes = self.beacon_l7_wrapper.send_command(self.TApdu_container.to_uper(), close)
        self.l7_transfer_kernel_lock.release()
        bcm_logger.info(f"Fragmented T-APDU response obtained from beacon in hex (UPER hex): {fragmented_t_apdu_with_get_response_bytes.hex().upper()}")

        bcm_logger.debug(f"Decoding received response T-APDU...")
        t_apdu_with_response_bytes = bytes(fragmented_t_apdu_with_get_response_bytes[1:])

        self.TApdu_container.from_uper(t_apdu_with_response_bytes)
        self.last_response_t_apdu_value = self.TApdu_container._val
        bcm_logger.info(f"Response T-APDU value: {self.last_response_t_apdu_value}")

        bcm_logger.info(f"Response T-APDU ASN1 decoding/representation: {self.TApdu_container.to_asn1()}")
        bcm_logger.info(f"Response T-APDU decoded with JER: {self.TApdu_container.to_jer()}")
        self.last_response_t_apdu_json = self.TApdu_container._to_jval()
        bcm_logger.debug(f"Response T-APDU in JSON: {self.last_response_t_apdu_json}")
        
        bcm_logger.info(f"Checking if T-APDU contains a return (ret) value (error code)...")
        try:
            return_code = self.last_response_t_apdu_value[1]["ret"]
            if return_code == 0:
                bcm_logger.info(f"Return code is present and is 0! (No errors)")
                bcm_logger.info(f"ReturnStatus ASN1 decoding: {EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.ReturnStatus.to_asn1()}")
            else:
                bcm_logger.error(f"Error code present! Return Code: {return_code}")
                EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.ReturnStatus.set_val(return_code)
                bcm_logger.error(f"ReturnStatus ASN1 decoding: {EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.ReturnStatus.to_asn1()}")
        except KeyError:
            bcm_logger.info(f"No return code in T-APDU! (No errors)")
        return self.last_response_t_apdu_json
    
    def decode_vst_parameter_from_eid(self, eid):
        bcm_logger.debug(f"Decoding VST parameter with EID {eid}...")
        parameter_bytes = self.get_parameter_bytes_from_eid_on_vst_value(eid)
        
        if parameter_bytes is None:
            return None
        decoded_parameter = custom_its_per_decoders.decode_vst_parameter_oct_str_bytes(parameter_bytes)
        return decoded_parameter
        
    def get_parameter_hex_str_from_eid_on_json_vst(self, eid:int, vst_json=None) -> str:
        if vst_json is None:
            vst_json = self.last_vst_json
        bcm_logger.debug(f"Getting hex VST parameter for EID {eid} from JSON VST {vst_json}")
        for application in vst_json['applications']:
            bcm_logger.debug(f"Application details: {application}")
            if application['eid'] == eid:
                return application['parameter']['octetstring']
        bcm_logger.error(f"EID {eid} is not present!")
        raise TransactionException('L7: EID not present!')
    
    def get_parameter_bytes_from_eid_on_vst_value(self, eid:int, vst_value=None) -> bytes:
        if vst_value is None:
            vst_value = self.last_vst_value
        bcm_logger.debug(f"Getting bytes VST parameter for EID {eid} from VST value {vst_value}")
        for application in vst_value['applications']:
            bcm_logger.debug(f"Application details: {application}")
            if application['eid'] == eid:
                parameter_value = application['parameter'][1]
                bcm_logger.info(f"Found EID {eid} in VST!!! Parameter value in hex: {parameter_value.hex().upper()}")
                return parameter_value
        bcm_logger.error(f"EID {eid} is not present!")
        raise TransactionException('L7: EID not present!')
    
    def compute_access_credentials(self, eid:int) -> bytes:
        bcm_logger.debug(f"Computing Access Credentials for EID {eid}...")
        decoded_vst_param = self.decode_vst_parameter_from_eid(eid)

        try:
            efc_cm = decoded_vst_param['EFC-ContextMark']
            ac_cr_key_ref = decoded_vst_param['AC_CR-KeyReference']
            rnd_obe = decoded_vst_param['RndOBE']

            access_credentials_int = dsrc_security.compute_access_credentials(efc_cm, rnd_obe, ac_cr_key_ref)
            access_credentials_bytes = access_credentials_int.to_bytes(4, 'big')
            return access_credentials_bytes
        except:
            return None
    
    def send_get_request(self, eid, accessCredentialsPresent:bool = False, attrIdList=None, close_transaction = False) -> EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.Get_Response:
        if accessCredentialsPresent:
            accessCredentials = self.compute_access_credentials(eid)
        else:
            accessCredentials = None
        # Get.Request is filled with 1 bit valued at 0
        get_req_value = {
            'eid': eid,
            'accessCredentials': accessCredentials,
            'attrIdList': attrIdList,
            'fill': (0, 1)
        }
        # Ignore keys in dict that map to None!!
        # That is, remove OPTIONAL elements that map to None
        # This is specially the case for the OPTIONAL accessCredentials
        get_req_value = {key: value for key, value in get_req_value.items() if value is not None}

        EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.Get_Request.set_val(get_req_value)
        bcm_logger.debug(f"Get.Request value: {EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.Get_Request._val}")
        bcm_logger.info(f"Get.Request in JER: {EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.Get_Request.to_jer()}")

        t_apdu_with_get_request_value = ('getRequest', get_req_value)
        json_encoded_response_t_apdu = self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_get_request_value, close=close_transaction)

        bcm_logger.debug("We now obtain the GET.response object from the T_APDU response!")
        bcm_logger.debug("GET.response is a parameterized type, so we cannot encode/decode it, only the T_APDU!")
        
        return json_encoded_response_t_apdu

    def send_action_request(self,
            mode=True,
            eid=0,
            actionType=0xA,
            accessCredentialsPresent:bool = True,
            actionParameter = None,
            iid = None,
            close_transaction = False):
        if accessCredentialsPresent:
            accessCredentials = self.compute_access_credentials(eid)
        else:
            accessCredentials = None
        if not actionParameter:
            actionParameter = ('setmmirq', 0)
        bcm_logger.debug(f"Preparing an ACTION.request...")
        bcm_logger.info(f"ActionType value is '{actionParameter[0]}'")

        # ACTION.request has a parameter, which needs to be inside a container
        EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.EfcContainer.set_val(actionParameter)
        parameter_tag = EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.EfcContainer._tag

        bcm_logger.debug(f"ActionParameter is an EfcContainer of Type {actionParameter[0]} (tag {parameter_tag}) value decoded with JER: {EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.EfcContainer.to_jer()}")
        bcm_logger.debug(f"Same value but APER-encoded in hex: {EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.EfcContainer.to_aper().hex().upper()}")
        
        action_request_value = {
            'mode': mode,
            'eid': eid,
            'actionType': actionType,
            'accessCredentials': accessCredentials,
            'actionParameter': actionParameter,
            'iid': iid
            }
        bcm_logger.debug(f"ACTION.request value: {action_request_value}")

        # Ignore keys in dict that map to None!!
        # That is, remove OPTIONAL elements that map to None
        # This is specially the case for the OPTIONAL accessCredentials and iid
        action_request_value = {key: value for key, value in action_request_value.items() if value is not None}

        t_apdu_with_action_req_value = ('actionRequest', action_request_value)
        bcm_logger.debug(f"T-APDU with ACTION.request value: {t_apdu_with_action_req_value}")

        self.TApdu_container.set_val(t_apdu_with_action_req_value)
        bcm_logger.info(f"T-APDU with ACTION.request in ASN: {self.TApdu_container.to_asn1()}")
        bcm_logger.info(f"T-APDU with ACTION.request in JER: {self.TApdu_container.to_jer()}")
        bcm_logger.info(f"ACTION.request with ActionType {actionType} and actionParameter of type {actionParameter[0]} being now sent...")

        json_encoded_response_t_apdu = self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_action_req_value, close_transaction)
        return json_encoded_response_t_apdu
    
    def presentation_request(self,
            eid:int,
            accessCredentialsPresent:bool = True,
            attrIdList=[],
            operator_auk_ref=111,
            close_transaction=False):
        return self.send_get_stamped_request(eid, accessCredentialsPresent, attrIdList, operator_auk_ref, close_transaction)
    
    def send_get_stamped_request(self,
            eid:int,
            accessCredentialsPresent:int = True,
            attrIdList=[],
            operator_auk_ref=111,
            close=False):
        bcm_logger.debug("Preparing an ActionParameter for an Action-Request of type GET_STAMPED.request (Presentation request)...")
        get_stamped_rq_value = self.get_stamped_request_action_parameter_preparation(eid, attrIdList, operator_auk_ref)

        bcm_logger.debug("Putting the GetStampedRq inside a 'gstrq' EFC Container...")
        container_with_get_stamped_rq_value = ('gstrq', get_stamped_rq_value)
        bcm_logger.debug(f"Container with GetStampedRq value: {container_with_get_stamped_rq_value}")

        # ActionType is 0 for GET_STAMPED.request and Mode is True (Always expects a response)
        json_encoded_response_t_apdu = self.send_action_request(True, eid, 0, accessCredentialsPresent, container_with_get_stamped_rq_value, close_transaction=close)

        bcm_logger.debug("We now obtain the GET_STAMPED.response object from the T_APDU response!")
        bcm_logger.debug("GET_STAMPED.response is a parameterized type, so we cannot encode/decode it, only the T_APDU!")

        bcm_logger.debug("We now obtain the GetStampedRq object in the ACTION.Response's parameter!")
        bcm_logger.debug("GET_STAMPED.response is a parameterized type, so we cannot encode/decode it, only the T_APDU!")

        try:
            action_response_parameter = self.last_response_t_apdu_value[1]['responseParameter']
            self.get_stamped_response_value = action_response_parameter[1]
            bcm_logger.info(f'GetStampedRq value: {self.get_stamped_response_value}')

            bcm_logger.debug(f"GET_STAMPED.response (Presentation response): {json_encoded_response_t_apdu['actionResponse']['responseParameter']}")
        except KeyError:
            bcm_logger.error(f"Reponse Parameter not present in GET_STAMPED.reponse!")
        return json_encoded_response_t_apdu
    
    def verify_obe_authenticity(self, get_stamped_action_response_value=None, efc_cm=None):
        if get_stamped_action_response_value is None:
            get_stamped_action_response_value = self.last_response_t_apdu_value[1]
        try:
            get_stamped_rs = get_stamped_action_response_value['responseParameter'][1]
        except:
            bcm_logger.error('No responseParameter in GET_STAMPED.response!!!')
            return

        if get_stamped_rs is None:
            get_stamped_rs = self.get_stamped_response_value
        if self.get_stamped_response_value is None:
            bcm_logger.error("No GET_STAMPED.response to verify!!")
        if efc_cm is None:
            eid = get_stamped_action_response_value['eid']
            decoded_vst_param = self.decode_vst_parameter_from_eid(eid)
            efc_cm = decoded_vst_param['EFC-ContextMark']
        attributeList = get_stamped_rs['attributeList']
        bcm_logger.info(f'attributeList value: {attributeList}')

        container_with_attribute_list = ('attrList', get_stamped_rs['attributeList'])
        EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.EfcContainer.set_val(container_with_attribute_list)
        bcm_logger.info(f"EFC Container of Type/CHOICE 'attrList' value: {EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.EfcContainer._val}")

        attribute_list_bytes = EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.EfcContainer.to_uper()[1:]

        provided_authenticator = get_stamped_rs['authenticator']
        rnd_rse_bytes = self.rnd_rse_bytes_value
        bcm_logger.debug(f"RndRSE value in hex: {rnd_rse_bytes.hex().upper()}")
        rnd_rse_int = int.from_bytes(rnd_rse_bytes, 'big')

        pan_bytes = get_stamped_rs['attributeList'][0]['attributeValue'][1]['personalAccountNumber']
        pan_id = pan_bytes.hex().upper()
        bcm_logger.info(f"PAN bytes in hex (PAN ID): {pan_id}")

        authenticator = dsrc_security.compute_authenticator_with_auk_ref(pan_id, efc_cm, attribute_list_bytes, rnd_rse_int, 115)

        bcm_logger.debug(f"Authenticator provided by OBE (UPER hex): {provided_authenticator.hex().upper()}")
        bcm_logger.debug(f"Authenticator computed by RSE (UPER hex): {authenticator.hex().upper()}")

        if provided_authenticator != authenticator:
            bcm_logger.error(f"The device/OBE is fraudulent!!")
        else:
            bcm_logger.info(f"The device/OBE is authentic!!!")
    def update_rnd_rse(self):
        bcm_logger.debug(f"Updating DateAndTime/SessionTime value (to be used as RndRSE value)...")

        EFC_CCC_LAC_asn1_objs.EfcDataDictionary.DateAndTime.set_val({ 
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

        bcm_logger.debug(f"RndRSE or SessionTime value (of type DateAndTime) in JER: {EFC_CCC_LAC_asn1_objs.EfcDataDictionary.DateAndTime.to_jer()}")
        self.rnd_rse_bytes_value = EFC_CCC_LAC_asn1_objs.EfcDataDictionary.DateAndTime.to_uper()

        bcm_logger.debug(f"RndRSE value (UPER hex): {self.rnd_rse_bytes_value.hex().upper()}")
        return self.rnd_rse_bytes_value
    def get_stamped_request_action_parameter_preparation(self, eid:int, attrIdList:list = [], operator_auk_ref=111):
        """
        ACTION.request of type GET_STAMPED.request (ActionType=0).

        The ActionParameter is thus of type GetStampedRs
        """
        if not attrIdList:
            attrIdList = []

        bcm_logger.debug(f"Preparing a GET_STAMPED.request to get attributes with ids {attrIdList}")
        self.update_rnd_rse()

        get_stamped_rq_value = {
            'attributeIdList': attrIdList,
            'nonce': self.rnd_rse_bytes_value,
            'keyRef': operator_auk_ref
            }
        bcm_logger.debug(f"GetStampedRq value to be stored in definition: {get_stamped_rq_value}")
        EFC_CCC_LAC_asn1_objs.EfcDsrcApplication.GetStampedRq.set_val(get_stamped_rq_value)
        
        bcm_logger.debug(f"GetStampedRq value: {EFC_CCC_LAC_asn1_objs.EfcDsrcApplication.GetStampedRq._val}")
        bcm_logger.info(f"GetStampedRs in JER: {EFC_CCC_LAC_asn1_objs.EfcDsrcApplication.GetStampedRq.to_jer()}")
        return get_stamped_rq_value

    def set_mmi(self, eid=0, close=False):
        bcm_logger.debug(f"Preparing a SET_MMI.request")
        bcm_logger.debug(f"The function to send ACTION.requests is defined to send a SET_MMI by default if no arguments are provided!")

        set_mmi_request_value = 0
        # SetMMI is a parameterized type, so it needs to be inside a container
        set_mmi_efc_container_value = ('setmmirq', set_mmi_request_value)
        EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.EfcContainer.set_val(set_mmi_efc_container_value)
        bcm_logger.debug(f"EfcContainer of Type 69 (SET_MMI) value decoded with JER: {EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.EfcContainer.to_jer()}")
        bcm_logger.debug(f"EfcContainer of Type 69 (SET_MMI) value decoded with PER: {EFC_CCC_LAC_asn1_objs.EfcDsrcGeneric.EfcContainer.to_uper()}")
        
        # SetMMI ActionType is 0xA, or 10 in decimal
        set_mmi_action_request_val = {
            'mode': True,
            'eid': eid,
            'actionType': 0xA,
            'actionParameter': set_mmi_efc_container_value
            }
        
        t_apdu_with_set_mmi_action_req_value = ('actionRequest', set_mmi_action_request_val)
        bcm_logger.info(f"ACTION.request of Type 10 (SET_MMI) being now sent...")

        t_apdu_with_action_response = self.send_req_t_apdu_and_obtain_resp_t_apdu(t_apdu_with_set_mmi_action_req_value, close)
        return t_apdu_with_action_response
    def send_close_transaction_setmmi(self, eid=0):
        return self.set_mmi(eid, True)
    
    def cardme_transaction(self, eid, mand_applications=[1, 20, 29], accessCredentialsPresent=False):
        self.initialize_transaction(mand_applications=mand_applications)
        # Getting payment info!! (Core part)
        self.presentation_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[32])

        # Getting Receipt data...
        # self.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[33, 34])

        # Getting contract information...
        # self.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[4])

        # Getting Vehicle attributes...
        ## Getting LPN only first case errors occurs in the 'big' GET.request
        self.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[16])
        self.send_get_request(eid, accessCredentialsPresent=accessCredentialsPresent, attrIdList=[17, 18, 19, 20, 22])

        # Getting OBE info...
        # self.send_get_request(eid, False, attrIdList=[24, 25, 26])

        # Getting driver info...
        # self.send_get_request(eid, False, attrIdList=[27, 47])


        self.send_close_transaction_setmmi(eid)
    def get_all_attributes(self, eid, mand_applications=[1, 20, 29]):
        attrIdList = list(range(0, 128))
        return self.get_attributes_in_list(eid, attrIdList, mand_applications=mand_applications)

    def get_attributes_in_list(self, eid, attrIdList=[32], mand_applications=[1, 20, 29]):
        # Initialize transaction
        self.initialize_transaction(mand_applications=mand_applications)

        # Send GET.requests
        obtained_attrs = set()
        get_responses = []
        for attr in attrIdList:
            self.send_get_request(eid, True, attrIdList=[attr])
            try:
                if self.last_response_t_apdu_json['getResponse']['ret'] == 0:
                    bcm_logger.info(self.last_response_t_apdu_json['getResponse'])
                    obtained_attrs.add(attr)
                    get_responses.append(self.last_response_t_apdu_json['getResponse']['attributelist'])
            except:
                bcm_logger.info(self.last_response_t_apdu_json['getResponse'])
                obtained_attrs.add(attr)
                get_responses.append(self.last_response_t_apdu_json['getResponse']['attributelist'])
        bcm_logger.info(f"Obtained attributes: {obtained_attrs}")
        bcm_logger.info(f"Rejected attributes: {set(attrIdList).difference(obtained_attrs)}")

        bcm_logger.info(json.dumps(get_responses, indent=2))

        # Close transaction with a SET_MMI
        self.send_close_transaction_setmmi(eid)

        return obtained_attrs, get_responses