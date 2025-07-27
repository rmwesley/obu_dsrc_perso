// Setup OpenStreetMap
zoom = 18;
axxes_position = [45.7593685, 4.8557787]

// var map = L.map('map');
var map = L.map('map').setView(axxes_position, zoom);

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

var axxes_marker = L.marker(axxes_position);
axxes_marker.addTo(map);

// HTML handling functions
function trigger_search_from_input(){
    obu_id = device_id_input.value;
    send_http_req_and_display_transaction_info(obu_id);
}
function send_http_req_to_get_transaction_info(obu_id){
    obu_transaction_info_req = new Request('/dsrc-transactions/data/obus/' + obu_id)
    return fetch(obu_transaction_info_req)
    .then((response) => response.json())
}

function decode_jer_dsrc_wgs_84_lat_long(signed_lat_long_int){
    signed_lat_long_int += 2**31

    // Horrible 8 decimal chars encoding/decoding...
    lat_long_joined_str = signed_lat_long_int.toString(10).padStart(8, '0');

    before_decimal_point = lat_long_joined_str.substring(0, 2)
    after_decimal_point = lat_long_joined_str.substring(2, 8)
    lat_long_float_str = before_decimal_point + '.' + after_decimal_point
    lat_long_float = parseFloat(lat_long_float_str)

    return lat_long_float
}

function decode_jer_dsrc_wgs_84_position(gnss_status_data){
    longitude_float = decode_jer_dsrc_wgs_84_lat_long(gnss_status_data['lastGnssFixLon'])
    latitude_float = decode_jer_dsrc_wgs_84_lat_long(gnss_status_data['lastGnssFixLat'])
    return [latitude_float, longitude_float]
}

function create_circle_from_gnss_status_data(gnss_status_data){
    position = decode_jer_dsrc_wgs_84_position(gnss_status_data)
    // console.log(position)
    unix_ts = gnss_status_data['lastGnssFixTime']
    hdop = gnss_status_data['currentHdop']['hDop']

    return L.circle(position, {
        // color: 'blue',
        // fillColor: '#3030f0',
        color: 'red',
        fillColor: '#f03030',
        fillOpacity: '0.5',
        radius: 1,
    })
}

POPUP_DICT_KEY_FILTER = ['_id', 'position_info', 'creation_time', 'last_update_timestamp']
function filter_and_keep_only_position_and_time_data(transaction_info){
    filtered_dict = {}
    // for (const dict_key of POPUP_DICT_KEY_FILTER) {
    //     filtered_dict[dict_key] = transaction_info[dict_key]
    // }
    for (const key in transaction_info) {
        if (POPUP_DICT_KEY_FILTER.includes(key)){
            filtered_dict[key] = transaction_info[key]
        }
    }
    return filtered_dict
}

function transaction_info_popup_html_content(transaction_info){
    display_json_info = filter_and_keep_only_position_and_time_data(transaction_info)
    display_json_info_str = JSON.stringify(display_json_info, null, 2)
    popup_html_content = `<andypf-json-viewer data='${display_json_info_str}'></andypf-json-viewer>`
    popup_html_content += `<a href='../data/transactions/${transaction_info['_id']}'>See transaction data</a>`
    console.log(popup_html_content)
    return popup_html_content
}

function add_transaction_info_to_map(transaction_info){
    position_info = transaction_info['position_info']
    console.log(position_info)
    // Check for empty dict!
    if (Object.keys(position_info).length == 0) {
        console.log('Transaction without position_info!')
        console.error(transaction_info)
        return
    }
    circle = create_circle_from_gnss_status_data(position_info);

    popup_html_content = transaction_info_popup_html_content(transaction_info)
    circle.bindPopup(popup_html_content)
    circle.addTo(map);
}

function send_http_req_and_display_transaction_info(obu_id){
    send_http_req_to_get_transaction_info(obu_id)
    .then((response_body) => {
        response_body.forEach(add_transaction_info_to_map);
    });
}