var sending_gps_positions = false;
var gps_sharing_ws = null

function start_gps_position_sharing(){
    if (sending_gps_positions) return;
    sending_gps_positions = true;
 
    gps_sharing_ws = new WebSocket('wss://proud-cricket-sharp.ngrok-free.app/rse_gps/ws')
    gps_sharing_ws.onmessage = console.log
}
function stop_gps_position_sharing(){
    if (!sending_gps_positions) return;
    sending_gps_positions = false;

    gps_sharing_ws.close()
}