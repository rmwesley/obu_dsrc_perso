import os
import json

import logging
td_config_logger = logging.getLogger(__name__)

def get_default_toll_domain_name():
    try:
        with open(f'settings/default_td.txt') as txt_file:
            return txt_file.read()
    except FileNotFoundError:
        return 'TIS'

def update_default_toll_domain_name(new_default_td_name:str):
    current_default_td_name = get_default_toll_domain_name()

    if current_default_td_name == new_default_td_name:
        td_config_logger.debug(f"Default Toll Domain is already ({new_default_td_name}).")
        return

    with open(f'settings/default_td.txt', 'w') as txt_file:
        txt_file.write(new_default_td_name)
    td_config_logger.info(f"Config updated, default Toll Domain set to ({new_default_td_name}).")