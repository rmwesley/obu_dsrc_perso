import json
import asyncio
import tkinter
import tkinter.ttk

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from dsrc_l7 import dsrc_l7_rse

class TollDomainConfigException(Exception):
    pass

def _set_current_toll_domain(toll_domain_name):
    global available_toll_domains
    global current_toll_domain_name
    global td_list_index

    try:
        current_toll_domain_name = toll_domain_name
        td_list_index = available_toll_domains.index(current_toll_domain_name)
        print(f"Set Toll Domain to: {current_toll_domain_name}!")
    except:
        raise TollDomainConfigException('Default Toll Domain not valid (not in available TD list)!!!')

available_toll_domains = []
def refresh_td_config():
    global available_toll_domains

    with open('settings/toll_domain_config.json', 'r') as json_file:
        toll_domains_config = json.load(json_file)
    # Should be a list of str!!
    available_toll_domains = toll_domains_config["available_toll_domains"]

    _set_current_toll_domain(toll_domains_config["default_toll_domain_name"])

def create_relative_window(master_widget: tkinter.BaseWidget) -> tkinter.BaseWidget:
    root_x = master_widget.winfo_x()
    root_y = master_widget.winfo_y()
    dx = 30
    dy = 30

    relative_window = tkinter.Toplevel()
    # w = toplevel.winfo_width()
    # h = toplevel.winfo_height()  
    # toplevel.geometry("%dx%d+%d+%d" % (w, h, root_x + dx, root_y + dy))
    relative_window.geometry("+%d+%d" % (root_x + dx, root_y + dy))
    return relative_window

def __create_td_choice_dropdown_combobox(master_widget: tkinter.BaseWidget):
    td_choice_dropdown_combobox = tkinter.ttk.Combobox(
        master=master_widget,
        state='readonly',
        values=available_toll_domains,
        text="Choose default Toll Domain",
        width=25,
        height=5,
    )
    td_choice_dropdown_combobox.current(td_list_index)
    td_choice_dropdown_combobox.pack()
    return td_choice_dropdown_combobox

def _create_callback_to_update_toll_domain_from_dropdown_choice(combobox_dropdown:tkinter.ttk.Combobox):
    '''This method expects a combobox as a dependency.
    We then use it to create a callback function for event handlers to call!
    This callback function saves/updates the current/chosen Toll Domain!'''
    def _cb_save_td():
        chosen_toll_domain_name = combobox_dropdown.get()
        _set_current_toll_domain(chosen_toll_domain_name)

    return _cb_save_td

def _create_td_choice_dropdown_combobox_and_return_its_update_td_callback_func(master_widget: tkinter.BaseWidget):
    # Create the Combobox/dropdown with choices
    td_choice_dropdown_combobox = __create_td_choice_dropdown_combobox(master_widget)
    # Create a callback function. It is gonna be used/called by event handlers!
    _cb_save_td = _create_callback_to_update_toll_domain_from_dropdown_choice(td_choice_dropdown_combobox)
    return _cb_save_td

def __cb_update_toll_domain_from_dropdown_choice(combobox_dropdown:tkinter.ttk.Combobox):
    chosen_toll_domain_name = combobox_dropdown.get()
    _set_current_toll_domain(chosen_toll_domain_name)

def create_new_toll_domain_config_window(master_widget:tkinter.BaseWidget):
    # toll_domain_config_window = tkinter.Toplevel()
    toll_domain_config_window = create_relative_window(master_widget)
    _cb_save_td = _create_td_choice_dropdown_combobox_and_return_its_update_td_callback_func(toll_domain_config_window)

    btn_save_current_td = tkinter.Button(
        master=toll_domain_config_window,
        text="Save current Toll Domain",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
        command=_cb_save_td
    )
    btn_save_current_td.pack()

    return toll_domain_config_window

# Callback with Dependency Injection (global var)!
def _cb_new_toll_domain_config_window():
    global main_window
    create_new_toll_domain_config_window(main_window)

def new_beacon_config_window():
    beacon_config_window = tkinter.Toplevel()
    btn_change_default_beacon = tkinter.Button(
        master=beacon_config_window,
        text="Change default Beacon",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
    )
    btn_change_default_beacon.pack()
    btn_set_current_beacon = tkinter.Button(
        master=beacon_config_window,
        text="Set current Beacon",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
    )
    btn_set_current_beacon.pack()
    return beacon_config_window

def new_rse_commands_window():
    rse_commands_window = tkinter.Toplevel()

    btn_rse_set_config = tkinter.Button(
        master=rse_commands_window,
        text="Initialize RSE DSRC L7",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
        command=lambda:rse_event_loop.run_until_complete(dsrc_l7_rse.initialize_bcm())
    )
    btn_rse_set_config.pack()

    btn_rse_set_mode = tkinter.Button(
        master=rse_commands_window,
        text="Set beacon mode",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
        command=lambda:rse_event_loop.run_until_complete(dsrc_l7_rse.change_trx_mode('Transparent'))
    )
    btn_rse_set_mode.pack()

    btn_rse_transaction = tkinter.Button(
        master=rse_commands_window,
        text="CARDME Transaction!",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
        command=lambda:rse_event_loop.run_until_complete(
            future = dsrc_l7_rse.cardme_transaction(4, mand_applications=[1, 20, 29], set_mmi=False)
            )
    )
    btn_rse_transaction.pack()

def setup_beacon_client_app_main_window():
    global rse_event_loop
    global main_window

    main_window = tkinter.Tk()

    btn_toll_domain_config_popup = tkinter.Button(
        text="Toll Domain Configuration",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
        command=_cb_new_toll_domain_config_window
    )
    btn_toll_domain_config_popup.pack()

    btn_beacon_config_popup = tkinter.Button(
        text="Beacon Configuration",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
        command=new_beacon_config_window
    )
    btn_beacon_config_popup.pack()

    btn_rse_commands_popup = tkinter.Button(
        text="RSE Commands",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
        command=new_rse_commands_window
    )
    btn_rse_commands_popup.pack()

    return main_window

# Main execution
if __name__ == "__main__":
    global rse_event_loop
    refresh_td_config()
    refresh_td_config = asyncio.new_event_loop()

    main_window = setup_beacon_client_app_main_window()
    main_window.mainloop()