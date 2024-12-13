export default {
    data() {
      return {
        beacon_state: '',
        transaction_initialized: false,
        last_vst: '',
        toll_chargers: ['Charger1', 'Charger2'], // Example data
        transaction_types: ['CARDME', 'PISTA'], // Example data
        toll_charger: '',
        transaction_type: '',
        deviceStyleCss: "device_error",
        isHidden: true
      }
    },
    created() {
      this.getBeaconState()
      this.getLastTransactionInitData()
    },
    methods: {
      showEverything(){
        this.isHidden = false
      },
      hideEverything(){
        this.isHidden = true
      },
      async initializeBeaconManager() {
        await fetch('/beacon/initialize-beacon-manager', { method: 'POST' })
        this.beacon_manager_initialized = true
      },
      async resetBeacon() {
        await fetch('/beacon/reset-beacon', { method: 'POST' })
      },
      async stopBeacon(){
        const response = await fetch('/beacon/change-mode', { method: 'POST', body: JSON.stringify({ mode_name: 'Stopped' }), headers: { 'Content-Type': 'application/json' } })
        const data = await response.json()
        this.beacon_state = data.beacon_state
      },
      async startTransactionLoop() {
        const response = await fetch('/beacon/loop-transactions', { method: 'POST', body: JSON.stringify({ loop_state: 'ON' }), headers: { 'Content-Type': 'application/json' } })
        const data = await response.json()
      },
      async stopTransactionLoop() {
        const response = await fetch('/beacon/loop-transactions', { method: 'POST', body: JSON.stringify({ loop_state: 'OFF' }), headers: { 'Content-Type': 'application/json' } })
        const data = await response.json()
      },
      async getBeaconState() {
        const response = await fetch('/beacon/beacon-state')
        const data = await response.json()
        this.beacon_state = data.beacon_state
      },
      async getLastTransactionInitData() {
        const response = await fetch('/beacon/last-transaction-init-data')
        const data = await response.json()
        this.last_vst = data.initialisationResponse
      },
      async changeToTransparent() {
        await fetch('/beacon/change-mode', { method: 'POST', body: JSON.stringify({ mode_name: 'Transparent' }), headers: { 'Content-Type': 'application/json' } })
      },
      async initializeTransaction() {
        await fetch('/beacon/initialize-transaction', { method: 'POST' })
        this.transaction_initialized = true
        this.getLastTransactionInitData()
      },
      async initializeAndCloseTransaction() {
        await fetch('/beacon/initialize-and-close-transaction', { method: 'POST' })
        this.getBeaconState()
        this.getLastTransactionInitData()
      },
      async closeTransaction(){
        await fetch('/beacon/send-close-transaction-echo-to-obu', { method: 'POST' })
        this.getBeaconState()
      },
      async efcGet() {
        // Implement EFC GET functionality
      },
      async efcSet() {
        // Implement EFC SET functionality
      },
      async efcAction() {
        // Implement EFC ACTION functionality
      },
      async executeTransaction() {
        // Implement transaction execution functionality
      }
    }
  }