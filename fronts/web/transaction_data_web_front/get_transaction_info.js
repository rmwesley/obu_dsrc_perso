function trigger_search_transaction_info_from_input(){
    obu_id = device_id_input.value
    send_http_req_and_display_transaction_info(obu_id)
}

function send_http_req_to_get_transaction_info(obu_id){
    obu_transaction_info_req = new Request('/dsrc-transactions/data/obus/' + obu_id)
    return fetch(obu_transaction_info_req)
    .then((response) => response.json())
}

function send_http_req_and_display_transaction_info(obu_id){
    send_http_req_to_get_transaction_info(obu_id)
    .then((response_body) => {
        // console.log(response_body)
        response_body.forEach(transaction_info => {
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
            // transaction_id = transaction_info[_id]
            transaction_id = new_row.cells[0].innerText;
            display_transaction_data_dialog_box(transaction_id);
            event.stopPropagation();
        })
        });
    }
    )
}