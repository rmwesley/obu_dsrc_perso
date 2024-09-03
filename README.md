Required PIP libraries:
- baudot
- pycryptodome
- logging
- threading
- requests_pkcs12

# Rememeber to set the MK_PATH environment variable!
This is the variable containing the path to the masterkey sets used for DSRC key derivation.
To do so, either run the main class or run the following command on PowerShell:
`$env:MK_PATH = Resolve-Path '..\..\master_keys_test.json' | select -ExpandProperty Path`

You can also directly set this environment variable in Python code like so:
`os.environ['MK_PATH'] = r"..\..\master_keys_test.json"`

This is exactly the code that is executed in the `main.py` module to set the `MK_PATH` environment variable

# Usage exemples
## Doing a hardcoded DSRC reading by executing main.py
To execute main.py on the windows command line (cmd) or on PowerShell, just run:
`.venv\Scripts\python.exe main.py`

## Recalculating the derived keys for an instance in a personalization's request body (JSON)
Inside the `devices/` subfolder, you will find some python modules to update personalization requests!

You need to put the original personalization inside the `perso_db.json` file.
Then, also update the `pan_ids_to_update` variable (hardcoded for now).
The, also update the masterkeys to be used in the `master_keys_test.json`.

After doing these 3 things, you can finally run the script :
`.venv\Scripts\python.exe -m devices.update_derived_keys_in_perso`

Then just take the contents of `proxy_format.json` and send it to the Proxy.


# Installing dependencies
For the time being we cannot run scripts.
So manually install dependencies with `pip`, which can be run via `python`.
Exemple:
`.venv\Scripts\python.exe -m pip install requests_pkcs12`

# Deploying the FastAPI in development mode
To deploy the FastAPI, just run:
`.venv\Scripts\fastapi.exe dev .\api_main.py`
The main UI (HMI) is contained in the index.html file and it is served in the root.
So just go to localhost:8000 in your browser to view the index.
To view FastAPI's Swagger UI instead, visit localhost:8000/docs.

# Using PIP to install packages in the venv
To install packages, just run:
`.venv\Scripts\python.exe main.py`