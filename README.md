As of now, only 32-bit Python can be used to manage the GEA TGBV beacon!!
This is because the DLL was compiled for 32-bit systems.

I recommend installing a 32-bit Python and creating a venv with it:

Use `where.exe` to find the install location for your Python interpreter!
Usually it is found at %AppData%\Local\Programs\Python\Python3-32\python.exe on Windows!!
Then simply run:
`C:\Users\Admin\AppData\Local\Programs\Python\Python312-32\python.exe -m venv .venv`
to create a virtual environment at `.venv`!

Sadly you will also need **Microsoft Visual C++ 14.0** or greater for installing fastapi on Windows (To build the `httptools` Python package):
https://visualstudio.microsoft.com/visual-cpp-build-tools/

Specifically, I installed Microsoft's Visual Studio **Build Tools** and then built the following dependencies:
- MSVC v143 - VS 2022 C++ x64/x86 Build Tools
- Windows 11 SDK (10.0.22621.0)

Required PIP packages for running beacon code:
- pycrate
- pycryptodome
- logging
- threading

Required packages for beacon proxy MQTT communication:
- paho-mqtt
- aiomqtt

Required dependencies for deploying FastAPI app:
- fastapi[standard]

Required dependencies for EFC decoder:
- requests_pkcs12
- baudot

Required dependencies for DSRC security interface:
- iso3166
- baudot

Required dependencies for DM API tests:
- azure-cosmos
- aiohttp
- requests_oauthlib
- jsondiff

# Rememeber to copy the `master_keys.json` file!
TODO: Securely handle secrets instead of keeping them in plaintext on a json file!!


# Rememeber to set the MK_PATH environment variable!
This is the variable containing the path to the masterkey sets used for DSRC key derivation.
To do so, either run the main class or run the following command on PowerShell:
`$env:MK_PATH = Resolve-Path '..\master_keys.json' | select -ExpandProperty Path`

You can also directly set this environment variable in Python code like so:
`os.environ['MK_PATH'] = r"..\master_keys.json"`

This is exactly the code that is executed in the `main.py` module to set the `MK_PATH` environment variable

# MQTT setup
Please start an MQTT broker and set up its connection info in the `settings/mqtt_broker_config.json` config file.
For example, you can install the Eclipse Mosquitto MQTT broker on a machine and setup its connection info in the local config file.

Just add the following to the `C:\Program Files\mosquitto\mosquitto.conf` config file on the remote machine:
```
# Plain MQTT protocol
listener 8333
# Enable logging
log_dest file c:\ProgramData\mosquitto\log\mosquitto.log
log_type all
```
And then use the 8333 port to communicate with the Mosquitto MQTT broker! :)

You can also setup a password file for the broker with the `mosquitto_passwd` command-line utility:
`mosquitto_passwd -c C:\ProgramData\mosquitto\password.txt beacon_proxy`
Then simply enter the password twice (to confirm it).

And then finally simply add a line to the `C:\Program Files\mosquitto\mosquitto.conf` file to
reference the file containing the encrypted credentials that was just created:
```
password_file c:\ProgramData\mosquitto\password.txt
```

# DM API tester setup
### DM database (Azure CosmosDB)
Remember to set the connection settings for the DM Database in the `../conn_settings/dm_db/dm_db_creds.json` config file.

### Microsoft Identity Platform OAuth 2.0 Web Application grant flow
Do the same for the config for the MIP access_token obtention for the DM API.
It is set on the `../conn_settings/dm_api/dm_api_auth_server_data.json` config file.

### DM API deployment date and benchmark lookup date settings for non-reg tests
To do the comparison non-regression tests, you need to manually set two dates in the `settings/dm_api_tester_config.json` config file.
The first is the start date for the Kapsch T6 benchmarks lookup.
The second is the end date for the benchmarks lookup and also the deployment date of the new DM version.
In a further update, it would be ideal to make these 4 separate dates, with end dates for the new DM version and for the benchmark lookups being optional (2 required).

## DM JWT Access token obtention/update
We use the `requests_oauthlib` Python package to get the access_token:
https://requests-oauthlib.readthedocs.io/en/latest/oauth2_workflow.html#web-application-flow

After the configuration is done, get the access_token JWT by running the `devices/perso_comparer/dm_api_client_auth.py` module and following the CLI instructions.
For example, run:
```
python3 devices/perso_comparer/dm_api_client_auth.py
```
And then copy-paste the redirect-uri in the terminal.
The access_token will be stored in the `devices/perso_comparer/last_dm_jwt.txt` local file

# Usage exemples
## Doing a hardcoded DSRC reading by executing main.py
To execute main.py on the windows command line (cmd) or on PowerShell, just run:
`.venv\Scripts\python.exe main.py`

## Recalculating the derived keys for an instance in a personalization's request body (JSON)
Inside the `devices/` subfolder, you will find some python modules to update personalization requests!
Here I describe the procedure to generate a new personalization request json file with the derived keys recalculated and updated.

1. Remember to set the correct keyset name in the MasterKey file json.
You need to put the original personalizations inside the `perso_db.json` file.
It is a JSON mapping each PAN to a unique personalization request.
I manually updated the EFC-CM values (attribute 0) for the Asfinag (EG) instance for the MEDIA EG devices.

2. Then, also update the `pan_ids_to_update` list (hardcoded for now) in the `update_derived_keys_in_perso.py` module.
These are the only PANs that are going to be updated.

3. Finally, update the masterkeys to be used in the `master_keys.json` file.

After doing these 3 things, you can finally run the script :
`.venv\Scripts\python.exe -m devices.update_derived_keys_in_perso`

Then just take the contents of `proxy_format_fix.json` or `proxy_format_full.json`, validate and verify it, and send it to the Proxy.
Use the `check_derived_keys.py` Python module to verify the derived keys.
I also recommend to take the latest personalization sent and compare (do a diff) with the newly prepared one to confirm that only the attributes 111 through 118 and 120 were modified.

# Generating SST004 InfoExchange Trust Objects for BALM (ISO 12855)
Simply run `.venv\Scripts\python.exe TC_EETS_mks\sst004_xml_preparation.py`

# Installing dependencies
For the time being we cannot run scripts.
So manually install dependencies with `pip`, which can be run via `python`.
Exemple:
`.venv\Scripts\python.exe -m pip install requests_pkcs12`

# Deploying the Main FastAPI application with all 4 subapps
To deploy the Main FastAPI app on localhost:8000, just run:
`.venv\Scripts\fastapi.exe dev .\efc_decoding_api_main.py`
Or deploy it with uvicorn:
` .\.venv\Scripts\python.exe -m uvicorn main_app:app --host 127.0.0.1 --port 8001`
For some reason, the `beacon_client_app` is deployed if the main app is not named `app` when deploying with FastAPI.

# Deploying the EFC decoding FastAPI in development mode
To deploy the EFC decoding FastAPI on localhost:8000, just run:
`.venv\Scripts\fastapi.exe dev .\efc_decoding_api_main.py`
or even `.venv\Scripts\fastapi.exe dev efc_decoding_api_main.py --port 8001` if the port 8000 is occupied.

The main UI (HMI) is contained in the index.html file and it is served in the root.
So just go to localhost:8000 in your browser to view the index.
To view FastAPI's Swagger UI instead, visit localhost:8000/docs.

# Deploying the Beacon Client API in development mode
To deploy the RSE FastAPI on localhost:8000, just run:
`.venv\Scripts\fastapi.exe dev .\beacon_client_api_main.py`
This API includes the /beacon router as well as routers for the Beacon Proxy Server to
use and communicate with to consult the state of the beacon/rse device or even synchronize data.

# Deploying the RSE FastAPI in development mode
To deploy the RSE FastAPI on localhost:8000, just run:
`.venv\Scripts\fastapi.exe dev .\rse_api_main.py`
This API includes only the /beacon router only

# Web and GUI front-end development
All the files for the multiple Web and GUI frontends are located in the `fronts/` directory.
They are split in `web/` and `gui/` directories for clarity.

# Using PIP to install packages in the venv
To install packages, just run:
`.venv\Scripts\python.exe main.py`

# Test BacL2 Beacon
The `Test_BacL2_beacon` beacon, shown in the `beacon_manager_config.json` config file uses a Virtual COM port.
To set it up in Windows, use the Null-modem emulator (com0com) serial port driver.
Use its `setupg` utility to manage the virtual COM ports.