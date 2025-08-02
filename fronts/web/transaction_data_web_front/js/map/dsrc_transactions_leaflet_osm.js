// Setup OpenStreetMap
zoom = 18;
axxes_position = [45.7593685, 4.8557787]

// var map = L.map('map');
var map = L.map('map').setView(axxes_position, zoom);

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
}).addTo(map);

td_zones_req = new Request('/td_zones/files/td_zones_geojson.json')
td_zones_geojson_features = fetch(td_zones_req)
    .then((response) => response.json())
    .then((td_zones_geojson) => {
        L.geoJSON(td_zones_geojson)
            .bindPopup((layer) => {
                console.log(layer.feature)
                return layer.feature.properties.TollDomain
            })
            .addTo(map)
        L.tileLayer
        // console.log(td_zones_geojson)
    });

// Add Axxès marker directly to map!
var axxes_marker = L.marker(axxes_position);
axxes_marker.addTo(map);

obuDsrcTransactionsInfoLeafletLayer = L.layerGroup()
obuDsrcTransactionsInfoLeafletLayer.addTo(map)

function send_http_req_to_get_transaction_info(obu_id, search_query_params){
    // obu_transaction_info_req = new Request('/dsrc-transactions/data/obus/' + obu_id + '/?skip=0&limit=400')
    query_str = new URLSearchParams(search_query_params).toString()
    obu_transaction_info_req = new Request(`/dsrc-transactions/data/obus/${obu_id}/?${query_str}`)
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

function compute_radius_from_hdpop(hdop){
    if (hdop == 0) return 1;
    return hdop + 1/hdop;
}

function create_circle_from_gnss_status_data(gnss_status_data){
    position = decode_jer_dsrc_wgs_84_position(gnss_status_data)

    // INTERPOLATED POSITION!!
    if (gnss_status_data['interpolated']) {
        return L.circle(position, {
            // color: 'blue',
            // fillColor: '#3030f0',
            color: 'green',
            fillColor: 'green',
            fillOpacity: '0.5',
            radius: 1,
        })
    }

    // console.log(position)
    // unix_ts = gnss_status_data['lastGnssFixTime']
    hdop = gnss_status_data['currentHdop']['hDop']

    return L.circle(position, {
        // color: 'blue',
        // fillColor: '#3030f0',
        color: 'red',
        fillColor: 'red',
        fillOpacity: '0.5',
        radius: compute_radius_from_hdpop(hdop),
    })
}

function create_line_between_gnss_fixes(gnss_fix_1_data, gnss_fix_2_data){
    if (!gnss_fix_1_data) return;
    line_start = decode_jer_dsrc_wgs_84_position(gnss_fix_1_data);
    line_end = decode_jer_dsrc_wgs_84_position(gnss_fix_2_data);
    return L.polyline([line_start, line_end], {color: 'blue'})
}
function add_line_between_gnss_fixes_to_map(gnss_fix_1_data, gnss_fix_2_data){
    line = create_line_between_gnss_fixes(gnss_fix_1_data, gnss_fix_2_data);
    if (line) line.addTo(obuDsrcTransactionsInfoLeafletLayer);
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
    // popup_html_content += `<a href='../data/transactions/${transaction_info['_id']}'>See transaction data</a>`
    popup_html_content += `<a href='search.html?transaction_id=${transaction_info['_id']}'>See transaction data</a>`
    return popup_html_content
}

function transaction_info_contains_position_data(transaction_info){
    position_info = transaction_info['position_info'];
    // Check for empty dict!
    return position_info != undefined && Object.keys(position_info).length > 0;
}

function add_transaction_info_to_map(transaction_info){
    circle = create_circle_from_gnss_status_data(position_info);

    popup_html_content = transaction_info_popup_html_content(transaction_info)
    circle.bindPopup(popup_html_content)
    circle.addTo(obuDsrcTransactionsInfoLeafletLayer);
    return true
}

function send_http_req_and_display_transaction_info(obu_id, search_query_params){
    send_http_req_to_get_transaction_info(obu_id, search_query_params)
    .then((response_body) => {
        let previous_gnss_fix = null
        var failure_count = 0
        for (const transaction_info of response_body){
            if (!transaction_info_contains_position_data(transaction_info)) continue;
            result = add_transaction_info_to_map(transaction_info);
            failure_count += result ? 0 : 1;

            add_line_between_gnss_fixes_to_map(previous_gnss_fix, transaction_info['position_info'])
            previous_gnss_fix = transaction_info['position_info']
        }
        return [response_body.length - failure_count, failure_count]
    }).then(([success_count, failure_count]) => {
        console.info(`Displayed ${success_count} transactions on map!`)
        if (failure_count > 0) console.error(`A total of ${failure_count} transactions could not be displayed`)
    });
}

// Main HTML input handling functions
function convert_local_date_to_iso8601_utc_datetime_str(local_date_str){
    local_date_obj = new Date(local_date_str)
    iso8601_utc_dt_str = local_date_obj.toISOString()
    console.log(iso8601_utc_dt_str)
    return iso8601_utc_dt_str
}
function trigger_search_from_input(){
    obu_id = device_id_input.value
    start_utc_dt_str = convert_local_date_to_iso8601_utc_datetime_str(search_start_time.value)
    end_utc_dt_str = convert_local_date_to_iso8601_utc_datetime_str(search_end_time.value)

    search_query_params = {
        'skip': 0,
        'limit': 100,
        'since_dt': start_utc_dt_str,
        'until_dt': end_utc_dt_str,
        'add_gnss_fix_deltas': false,
        'interpolate_missing_gnss_fixes': interpolate_positions_checkbox.checked,
    }
    send_http_req_and_display_transaction_info(obu_id, search_query_params);
}
function clear_obu_transactions_layer_on_leaflet_map(){
    obuDsrcTransactionsInfoLeafletLayer.clearLayers();
}