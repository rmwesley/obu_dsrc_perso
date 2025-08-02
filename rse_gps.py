from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from starlette.websockets import WebSocketDisconnect

rse_gps_app = FastAPI()

@rse_gps_app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print('GPS WS: Connected!!')
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            print(data)
    except WebSocketDisconnect:
        print('GPS WS: Disconnected!!')