Required PIP libraries:
- baudot
- pycryptodome
- logging
- threading


# Deploying the FastAPI in development mode
To deploy the FastAPI, just run:
`.venv\Scripts\fastapi.exe dev .\api_main.py`
The main UI (HMI) is contained in the index.html file and it is served in the root.
So just go to localhost:8000 in your browser to view the index.
To view FastAPI's Swagger UI instead, visit localhost:8000/docs.

# Executing main.py
To execute main.py on the windows command line (cmd) or on PowerShell, just run:
`.venv\Scripts\python.exe main.py`

# Using PIP to install packages in the venv
To install packages, just run:
`.venv\Scripts\python.exe main.py`