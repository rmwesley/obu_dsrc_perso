function send_http_req_to_get_transaction_data(transaction_id){
    transaction_data_req = new Request('/dsrc-transactions/data/transactions/' + transaction_id)
    return fetch(transaction_data_req)
    .then((response) => response.json())
};

transaction_data_dialog_display_content.addEventListener('click', (event) => {
    console.log("Transactions data dialog evt:");
    console.log(event);
    console.log(event.target);
    event.stopPropagation();
});

document.body.addEventListener('click', (event) => {
    console.log("Body evt:");
    console.log(event);
    transaction_data_display.close()
});

function display_transaction_data_dialog_box(transaction_id){
    transaction_data_display.showModal();
    send_http_req_to_get_transaction_data(transaction_id).then((response_body) => {
    indent_spaces = 2
    transaction_data_dialog_display_content.innerHTML = JSON.stringify(response_body, null, indent_spaces)
    })
}