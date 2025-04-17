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

Required dependencies for deploying FastAPI app:
- fastapi[standard]

Required dependencies for EFC decoder:
- requests_pkcs12
- baudot

Required dependencies for DSRC security interface:
- iso3166
- baudot

Required dependencies for DM tests:
- azure-cosmos

# Rememeber to copy the `master_keys.json` file!
TODO: Securely handle secrets instead of keeping them in plaintext on a json file!!


# Rememeber to set the MK_PATH environment variable!
This is the variable containing the path to the masterkey sets used for DSRC key derivation.
To do so, either run the main class or run the following command on PowerShell:
`$env:MK_PATH = Resolve-Path '..\master_keys.json' | select -ExpandProperty Path`

You can also directly set this environment variable in Python code like so:
`os.environ['MK_PATH'] = r"..\master_keys.json"`

This is exactly the code that is executed in the `main.py` module to set the `MK_PATH` environment variable

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

# Deploying the EFC decoding FastAPI in development mode
To deploy the EFC decoding FastAPI on localhost:8000, just run:
`.venv\Scripts\fastapi.exe dev .\efc_decoding_api_main.py`
or even `.venv\Scripts\fastapi.exe dev efc_decoding_api_main.py --port 8001` if the port 8000 is occupied.
The main UI (HMI) is contained in the index.html file and it is served in the root.
So just go to localhost:8000 in your browser to view the index.
To view FastAPI's Swagger UI instead, visit localhost:8000/docs.

# Deploying the RSE FastAPI in development mode
To deploy the RSE FastAPI on localhost:8000, just run:
`.venv\Scripts\fastapi.exe dev .\rse_api_main.py`
or even `.venv\Scripts\fastapi.exe dev rse_api_main.py --port 8001` if the port 8000 is occupied.

# Using PIP to install packages in the venv
To install packages, just run:
`.venv\Scripts\python.exe main.py`