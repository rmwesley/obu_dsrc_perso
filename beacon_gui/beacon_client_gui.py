import os
import asyncio
import tkinter

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from dsrc_l7 import dsrc_l7_rse

async def simple_bcm_cardme_transaction():
    asyncio.run()

def new_toll_domain_config_window():
    toll_domain_config_window = tkinter.Toplevel()
    btn_change_default_td = tkinter.Button(
        master=toll_domain_config_window,
        text="Change default Toll Domain",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
    )
    btn_change_default_td.pack()
    btn_set_current_td = tkinter.Button(
        master=toll_domain_config_window,
        text="Set current Toll Domain",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
    )
    btn_set_current_td.pack()
    return toll_domain_config_window

def setup_beacon_client_app_window():
    global rse_event_loop

    main_window = tkinter.Tk()

    btn_toll_domain_config = tkinter.Button(
        text="Toll Domain Configuration",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
        command=new_toll_domain_config_window
    )
    btn_toll_domain_config.pack()

    btn_rse_set_config = tkinter.Button(
        text="Initialize RSE DSRC L7",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
    )
    btn_rse_set_config.bind("<Button-1>", lambda event: rse_event_loop.run_until_complete(dsrc_l7_rse.initialize_bcm()))
    btn_rse_set_config.pack()

    btn_rse_set_mode = tkinter.Button(
        text="Set beacon mode",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
    )
    btn_rse_set_mode.bind("<Button-1>", lambda event: rse_event_loop.run_until_complete(dsrc_l7_rse.change_trx_mode('Transparent')))
    btn_rse_set_mode.pack()

    btn_rse_transaction = tkinter.Button(
        text="CARDME Transaction!",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
    )
    btn_rse_transaction.pack()
    
    btn_rse_transaction.bind("<Button-1>",
        func=lambda event: rse_event_loop.run_until_complete(
            future = dsrc_l7_rse.cardme_transaction(4, mand_applications=[1, 20, 29], set_mmi=False)
            )
        )

    return main_window

# Main execution
if __name__ == "__main__":
    global rse_event_loop
    rse_event_loop = asyncio.new_event_loop()

    main_window = setup_beacon_client_app_window()
    main_window.mainloop()