// Trigger search from HTML input functions
function trigger_search_transaction_info_from_hex_obu_id_input(){
    obu_id = hex_eq_obu_id_input.value
    send_http_req_and_display_transaction_info_list_for_obu_id(obu_id)
}

function trigger_search_transaction_info_from_dec_obu_id_input(){
    obu_id = parseInt(dec_eq_obu_id_input.value).toString(16)
    send_http_req_and_display_transaction_info_list_for_obu_id(obu_id)
}

function trigger_search_transaction_info_from_hex_pan_input(){
    pan_id = hex_pan_input.value
    send_http_req_and_display_transaction_info_list_for_pan(pan_id)
}

// HTTP request functions
function send_http_req_to_get_transaction_info_list_for_obu_id(obu_id){
    obu_transaction_info_req = new Request('/dsrc-transactions/data/obus/' + obu_id)
    // obu_transaction_info_req = new Request('/dsrc-transactions/data/obus/' + obu_id + '?interpolate_positions=True')
    return fetch(obu_transaction_info_req)
        .then((response) => response.json())
}
function send_http_req_to_get_transaction_info_list_for_pan(pan){
    obu_transaction_info_req = new Request('/dsrc-transactions/data/pans/' + pan)
    // obu_transaction_info_req = new Request('/dsrc-transactions/data/obus/' + obu_id + '?interpolate_positions=True')
    return fetch(obu_transaction_info_req)
        .then((response) => response.json())
}

function display_transaction_info_list(transaction_info_list){
    transaction_info_list.forEach(transaction_info => {
    let new_row = transactions_table.insertRow(-1)
    key_list = [
        '_id',
        'personalAccountNumber',
        'equOBUId',
        'creation_time',
        'last_update_timestamp',
    ]
    key_list.forEach((key) => {
        value = transaction_info[key]

        new_cell = new_row.insertCell(-1)
        text_value = document.createTextNode(value)
        new_cell.appendChild(text_value)
    })
    new_row.addEventListener('click', (event) => {
        console.log("Row evt: " + event);
        transaction_id = new_row.cells[0].innerText;
        display_transaction_data_dialog_box(transaction_id);
        event.stopPropagation();
    })
    });
}

function send_http_req_and_display_transaction_info_list_for_obu_id(obu_id){
    // The HTTP response payload is a transaction info list!
    send_http_req_to_get_transaction_info_list_for_obu_id(obu_id)
        .then(display_transaction_info_list)
}

function send_http_req_and_display_transaction_info_list_for_pan(pan){
    // The HTTP response payload is a transaction info list!
    send_http_req_to_get_transaction_info_list_for_pan(pan)
        .then(display_transaction_info_list)
}