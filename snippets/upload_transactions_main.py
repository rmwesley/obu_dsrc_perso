from services.db import transactions_data_sync

if __name__ == '__main__':
    transactions_data_sync.upload_local_data(size=None)