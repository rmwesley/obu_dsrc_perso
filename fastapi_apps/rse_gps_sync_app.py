from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketDisconnect

from ..toll_charging_security.tc_default_td_value_handler import update_default_toll_domain_name
from ..toll_domain_gis_zones.td_geometry_operations import get_td_name_from_gps_coords

rse_gps_td_app = FastAPI()

@rse_gps_td_app.websocket("/ws")
async def gps_sync_websocket_endpoint_to_update_default_td(websocket: WebSocket):
    print('GPS WS: Connected!!')
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # print(data)
            gps_coords = data['coords']
            td_name = get_td_name_from_gps_coords(gps_coords['latitude'], gps_coords['longitude'])
            update_default_toll_domain_name(td_name)
    except WebSocketDisconnect:
        print('GPS WS: Disconnected!!')