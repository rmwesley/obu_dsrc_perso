function trigger_search_transaction_info_from_transaction_id_input(){
    transaction_id = transaction_id_input.value;
    display_transaction_data_dialog_box(transaction_id);
}

function send_http_req_to_get_transaction_data(transaction_id){
    transaction_data_req = new Request('/dsrc-transactions/data/transactions/' + transaction_id);
    return fetch(transaction_data_req)
        .then((response) => response.json());
};

transaction_data_dialog_display_content.addEventListener('click', (event) => event.stopPropagation());
document.body.addEventListener('click', (event) => transaction_data_display.close());

function display_transaction_data_dialog_box(transaction_id){
    transaction_data_display.showModal();
    send_http_req_to_get_transaction_data(transaction_id).then((response_body) => {
        indent_spaces = 2
        transaction_data_dialog_display_content.innerHTML = JSON.stringify(response_body, null, indent_spaces)
    })
}