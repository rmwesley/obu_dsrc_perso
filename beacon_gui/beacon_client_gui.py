import os
import asyncio
import tkinter

# Importing the definitions of the Python DLL loader, mainly consisting of enums and foreign functions
# Function prototypes return foreign functions when called with a long pointer address, LPFN, as input
from dsrc_l7 import dsrc_l7_rse

async def simple_bcm_cardme_transaction():
    asyncio.run()

def setup_beacon_client_app_window():
    global rse_event_loop

    main_window = tkinter.Tk()

    # lbl_set_config = tkinter.Label(text="Set Beacon Config")
    # lbl_set_config.pack()
    btn_set_config = tkinter.Button(
        text="Initialize RSE DSRC L7",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
    )
    btn_set_config.bind("<Button-1>", lambda event: rse_event_loop.run_until_complete(dsrc_l7_rse.initialize_bcm()))
    # btn_set_config.bind("<Button-1>", lambda event: asyncio.ensure_future(dsrc_l7_rse.initialize_bcm()))
    btn_set_config.pack()

    # lbl_set_mode = tkinter.Label(text="Set Transparent Mode")
    # lbl_set_mode.pack()
    btn_set_mode = tkinter.Button(
        text="Set beacon mode",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
    )
    btn_set_mode.bind("<Button-1>", lambda event: rse_event_loop.run_until_complete(dsrc_l7_rse.change_trx_mode('Transparent')))
    # btn_set_mode.bind("<Button-1>", lambda event: asyncio.ensure_future(dsrc_l7_rse.change_trx_mode('Transparent')))
    btn_set_mode.pack()

    # lbl_transaction = tkinter.Label(text="Simple Transaction")
    # lbl_transaction.pack()
    btn_transaction = tkinter.Button(
        text="CARDME Transaction!",
        width=25,
        height=5,
        bg="blue",
        fg="yellow",
    )
    btn_transaction.pack()
    
    btn_transaction.bind("<Button-1>",
        func=lambda event: rse_event_loop.run_until_complete(
            future = dsrc_l7_rse.cardme_transaction(4, mand_applications=[1, 20, 29], set_mmi=False)
            )
        )
    # btn_transaction.bind("<Button-1>",
    #     func=lambda event: asyncio.ensure_future(
    #         future=dsrc_l7_rse.cardme_transaction(4, mand_applications=[1, 20, 29], set_mmi=False)
    #         )
    #     )

    return main_window

# async def init_beacon_management():
#     await dsrc_l7_rse.init_bcm_and_set_transparent_mode()

#     dsrc_l7_rse.set_beeping_state(beep_state=False)

# Main execution
if __name__ == "__main__":
    global rse_event_loop
    rse_event_loop = asyncio.new_event_loop()

    main_window = setup_beacon_client_app_window()
    main_window.mainloop()