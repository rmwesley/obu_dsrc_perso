var sending_gps_positions = false;
var gps_sharing_ws = null
var refreshIntervalId = null

function send_position(web_socket){
    // console.log('Sending packet...')
    navigator.geolocation.getCurrentPosition((position) => {
        // console.log(position)
        web_socket.send(JSON.stringify(position.toJSON()));
    });
}
function start_gps_position_sharing(){
    if (sending_gps_positions) return;
    sending_gps_positions = true;
 
    gps_sharing_ws = new WebSocket('wss://proud-cricket-sharp.ngrok-free.app/rse_gps/ws')
    gps_sharing_ws.addEventListener('error', (event) =>{
        window.alert(`WebSocket connection failure!!\n\n${event.target.url}`)
        });
    gps_sharing_ws.onmessage = console.log

    gps_sharing_ws.onopen = () => {
        console.log('Open!! Sharing position!')
        refreshIntervalId = setInterval(() => send_position(gps_sharing_ws), 1000)
    }
}
function stop_gps_position_sharing(){
    if (!sending_gps_positions) return;
    sending_gps_positions = false;

    gps_sharing_ws.close()
    clearInterval(refreshIntervalId)
}