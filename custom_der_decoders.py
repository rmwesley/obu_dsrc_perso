import logging

decoder_logger = logging.getLogger(__name__)

def decode_vst(vst_bytes, logger=decoder_logger):
    vst_data = {}
    decoder_logger.debug("Decoding VST...")
    decoder_logger.debug(vst_bytes.hex().upper())

    profile = vst_bytes[2]
    number_of_applications = vst_bytes[3]
    vst_byte_idx = 4

    decoder_logger.debug(f"\nProfile: {profile}")
    decoder_logger.debug(f"Number of applications: {number_of_applications}")

    applications = []
    # We now iterate over the applications (AID/EID pairs)...
    for aid_index in range(0, number_of_applications):
        current_application_details = {}

        decoder_logger.debug(f"Application {aid_index+1}:")

        eid_present = vst_bytes[vst_byte_idx] >> 7
        parameter_present = (vst_bytes[vst_byte_idx] >> 6) & 0x01

        # AID is 5 bits
        aid = vst_bytes[vst_byte_idx] & 0x1F
        current_application_details["AID"] = aid

        if aid == 1:
            decoder_logger.debug(f"\tAID: {aid} (EFC)")
        elif aid == 20:
            decoder_logger.debug(f"\tAID: {aid} (CCC)")
        elif aid == 29:
            decoder_logger.debug(f"\tAID: {aid} (UNI)")
        else:
            decoder_logger.debug(f"\tAID: {aid}")
        vst_byte_idx += 1

        if eid_present:
            eid = vst_bytes[vst_byte_idx]
            decoder_logger.debug(f"\tEID: {eid}")
            current_application_details["EID"] = eid
            vst_byte_idx += 1
        else:
            decoder_logger.debug(f"\tEID not present")
        if parameter_present:
            # Parameter/container here is always 2, for an octet string, EFC-CM
            # So the next 2 bytes are 0x02LL, the container type and size of the string
            # If size is 6, it is just an EFC-CM
            # If the size is 16 it contains access credentials
            container_type = vst_bytes[vst_byte_idx]
            container_length = vst_bytes[vst_byte_idx+1]
            decoder_logger.debug(f"\tContainer details: {bytes([container_type, container_length]).hex()}")

            if vst_bytes[vst_byte_idx] == 2:
                decoder_logger.debug(f"Container type (ASN1 tag) is {vst_bytes[vst_byte_idx]} for an Octet String")
            else :
                decoder_logger.error(f"Container type (ASN1 tag) is {container_type} instead of 02!!!")
    
            if container_length == 6:
                decoder_logger.debug(f"Length of Octet String is {container_length}, so we expect an EFC-CM only")
            elif container_length == 16:
                decoder_logger.debug(f"Last application!")
                decoder_logger.debug(f"Length of Octet String is {container_length}, so we expect an EFC-CM with access credentials right after!")
            else:
                decoder_logger.error(f"Length of Octet String is {container_length}, which should never happen in a VST parameter")
            vst_byte_idx += 2

            # And then we get the actual EFC-CM:
            efc_cm_hex_str = bytes(vst_bytes[vst_byte_idx : vst_byte_idx + 3]).hex().upper()
            decoder_logger.debug(f"\tEFC-CM: {efc_cm_hex_str}")
            current_application_details["EFC-CM"] = efc_cm_hex_str

            # Country code is encoded in 10 bits
            country_code = (vst_bytes[vst_byte_idx] << 2) + (vst_bytes[vst_byte_idx] >> 6)
            # Issuer identifier is encoded in 14 bits
            issuer_id = ((vst_bytes[vst_byte_idx] & 0x3F) << 8) + vst_bytes[vst_byte_idx+1]

            vst_byte_idx += 3

            # We now get the TOC and CV
            toc = (vst_bytes[vst_byte_idx] << 8) + vst_bytes[vst_byte_idx+1]
            cv = vst_bytes[vst_byte_idx+2]

            decoder_logger.debug(f"\tTOC: {toc:04X}")
            decoder_logger.debug(f"\tCV: {cv}")
            vst_byte_idx += 3

        else:
            decoder_logger.debug(f"\tEFC-CM not present")

        applications.append(current_application_details)
    vst_data["applications"] = applications

    # If the length of the last parameter container in the VST is 16, we have access credentials in it
    if container_length == 16:
        # Gettin Access Credentials data
        container_type = vst_bytes[vst_byte_idx]
        container_length = vst_bytes[vst_byte_idx+1]
        if container_type != 2 or container_length != 2:
            decoder_logger.error(f"Access Credentials container is {container_type:02X}{container_length:02X} instead of 0202")
        vst_byte_idx += 2

        decoder_logger.debug("Obtaining Access Credentials details...")
        ac_mk_ref = vst_bytes[vst_byte_idx]
        ac_cr_diversifier = vst_bytes[vst_byte_idx+1]
        vst_byte_idx += 2

        container_type = vst_bytes[vst_byte_idx]
        container_length = vst_bytes[vst_byte_idx+1]
        if container_type != 2 or container_length != 4:
            decoder_logger.error(f"Access Credentials container is {container_type:02X}{container_length:02X} instead of 0204")
        vst_byte_idx += 2

    rnd_obe = bytes(vst_bytes[vst_byte_idx : vst_byte_idx+4])
    vst_data["RndOBE"] = rnd_obe.hex().upper()

    decoder_logger.debug(f"\tRndOBE: {rnd_obe.hex().upper()}")
    vst_byte_idx += 4

    obe_status_present = vst_bytes[vst_byte_idx] & 0x80
    equipment_class = vst_bytes[vst_byte_idx] & 0x7F
    obe_manufacturer_id = vst_bytes[vst_byte_idx+1:vst_byte_idx+3]

    decoder_logger.debug(f"\tEquipment class: {equipment_class}")
    decoder_logger.debug(f"\tOBE manufacturerId: {int.from_bytes(obe_manufacturer_id)}")
    vst_byte_idx += 1

    if obe_status_present:
        obe_status = vst_bytes[vst_byte_idx]

    return vst_data