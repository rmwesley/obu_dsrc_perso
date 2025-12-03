import pathlib
import logging
td_config_logger = logging.getLogger(__name__)

package_root_dir = pathlib.Path(__file__).parent.parent
default_td_txt_path = package_root_dir / f'settings/default_td.txt'

def get_default_toll_domain_name():
    try:
        with default_td_txt_path.open() as txt_file:
            return txt_file.read()
    except FileNotFoundError:
        td_config_logger.error('No default TD set!! Using hardcoded value (TIS) instead.')
        return 'TIS'

def update_default_toll_domain_name(new_default_td_name:str):
    current_default_td_name = get_default_toll_domain_name()

    if current_default_td_name == new_default_td_name:
        td_config_logger.debug(f"Default Toll Domain is already ({new_default_td_name}).")
        return

    with default_td_txt_path.open('w') as txt_file:
        txt_file.write(new_default_td_name)
    td_config_logger.info(f"Config updated, default Toll Domain set to ({new_default_td_name}).")