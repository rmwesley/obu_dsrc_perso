from . import dsrc_l7_rse

class RseInitService:
    def __init__(self):
        self.initialized = False

    async def start(self):
        print('Initializing RSE beacon DSRC L7 stack...')
        if self.initialized:
            return

        try:
            self.initialized = True
            await dsrc_l7_rse.init_bcm_and_set_transparent_mode()
            print('Initialized DSRC beacon!')

        except Exception as e:
            print(repr(e))
            print('Please set the beacon configuration properly to initialize it via BAC L7!')
            await self.stop()

    async def stop(self):
        if not self.initialized:
            return

        await dsrc_l7_rse.change_trx_mode("Stopped")
        self.initialized = False
