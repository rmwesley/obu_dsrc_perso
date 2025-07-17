// Setup OpenStreetMap
zoom = 13;
x = 45.7593685;
y = 4.8557787;

// var map = L.map('map');
var map = L.map('map').setView([x, y], zoom);

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

var axxes_marker = L.marker([x, y]);
axxes_marker.addTo(map);

// HTML handling functions
function trigger_search_from_input(){
    obu_id = device_id_input.value;
    send_http_req_and_display_data(obu_id);
}
function send_http_req_to_get_data(obu_id){
    obu_transaction_data_req = new Request('/dsrc-transactions/data/obus/' + obu_id)
    return fetch(obu_transaction_data_req)
    .then((response) => response.json())
}
function send_http_req_and_display_data(obu_id){
    send_http_req_to_get_data(obu_id)
    .then((response_body) => {
        response_body.forEach(transaction_data => {
            console.log(transaction_data);
        });
    })
}