from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

from dsrc_security.dsrc_td_security_operations import set_toll_domain
from toll_domain_gis_zones.td_geometry_operations import get_td_name_from_gps_coords

rse_gps_app = FastAPI()

@rse_gps_app.websocket("/ws")
async def gps_websocket_endpoint(websocket: WebSocket):
    print('GPS WS: Connected!!')
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            print(data)
            gps_coords = data['coords']
            td_name = get_td_name_from_gps_coords(gps_coords['latitude'], gps_coords['longitude'])
            set_toll_domain(td_name)
            print(f"Set Toll Domain to: {td_name}")
    except WebSocketDisconnect:
        print('GPS WS: Disconnected!!')