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
- baudot
- iso3166
- axxes_asn_compiles
- custom_its_decoders
- pycryptodome
- logging
- threading

Required PIP packages for transaction data manager app:
- pymongo

Required packages for beacon proxy MQTT communication:
- paho-mqtt
- aiomqtt

Required dependencies for deploying FastAPI app:
- fastapi[standard]

Required dependencies for EFC decoder:
- pycrate
- axxes_asn_compiles
- requests_pkcs12
- baudot

Required dependencies for Toll Domain zones geography info app:
- pyshp
- shapely

# Rememeber to copy the `master_keys.json` file!
TODO: Securely handle secrets instead of keeping them in plaintext on a json file!!


# Rememeber to set the MK_PATH environment variable!
This is the variable containing the path to the masterkey sets used for DSRC key derivation.
To do so, either run the main class or run the following command on PowerShell:
`$env:MK_PATH = Resolve-Path '..\master_keys.json' | select -ExpandProperty Path`

You can also directly set this environment variable in Python code like so:
`os.environ['MK_PATH'] = r"..\master_keys.json"`

This is exactly the code that is executed in the `main.py` module to set the `MK_PATH` environment variable

# Installing dependencies
For the time being we cannot run scripts.
So manually install dependencies with `pip`, which can be run directly as a command or via `python -m pip`.
I recommend to crate a Python `.venv/` (can be done through VSCode) and then execute:
`.\.venv\Scripts\pip.exe install fastapi[standard] pymongo pycrate pycryptodome baudot iso3166 pyserial pyshp shapely`

# ASN PER decoding & encoding (dencoding procedures)
## pycrate ASN compiles
Add the path to the `axxes_asn_compiles` module to the **PYTHONPATH** environment variable.
## Custom Intelligent Transport System decoders
Add the path to the `custom_its_decoders` module to the **PYTHONPATH** environment variable.

# Usage exemples
## Doing a hardcoded DSRC reading by executing main.py
To execute main.py on the windows command line (cmd) or on PowerShell, just run:
`.venv\Scripts\python.exe main.py`

# Deploying the Main FastAPI application with all subapps
To deploy the Main FastAPI app on localhost:8000, just run:
`.venv\Scripts\fastapi.exe dev .\main_app.py`
Or deploy it with uvicorn:
` .\.venv\Scripts\python.exe -m uvicorn main_app:app --host 127.0.0.1 --port 8001`
For some reason, the `beacon_client_app` is deployed if the main app is not named `app` when deploying with FastAPI.

# Deploying the EFC decoding FastAPI in development mode
To deploy the EFC decoding FastAPI on localhost:8000, just run:
`.venv\Scripts\fastapi.exe dev .\main_app.py`
or even `.venv\Scripts\fastapi.exe dev main_app.py --port 8001` if the port 8000 is occupied.

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