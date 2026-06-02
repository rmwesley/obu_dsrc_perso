import datetime
import sqlite3

LOCAL_SQLLITE_DB_PATH = 'transactions.db'

class TransactionMetadataHandler:
    def __init__(self, db_path=LOCAL_SQLLITE_DB_PATH):
        self.db_path = db_path
        self._initialize_database()

    def _initialize_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transactionDataFileName TEXT,
                    transactionUuid TEXT,
                    rseTdName TEXT NOT NULL,
                    rseManufacturerId INTEGER,
                    beaconIndividualId INTEGER,
                    obeManufacturerId INTEGER,
                    equOBUId INTEGER,
                    personalAccountNumber BLOB,
                    licencePlateNumber BLOB,
                    lpnCountryCode TEXT,
                    authResult BOOLEAN DEFAULT FALSE,
                    positionLatitude REAL,
                    positionLongitude REAL,
                    creation_ts TEXT NOT NULL,
                    update_ts TEXT NOT NULL
                )
            ''')
            conn.commit()

    def create_transaction_with_init_data(self, td_name, initialization_request_jval, initialization_response_jval, transaction_log_filename, transaction_uuid):
        with sqlite3.connect(self.db_path) as conn:
            rseTdName = td_name

            creation_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
            update_ts = creation_ts

            rseManufacturerId = initialization_request_jval['initialisationRequest']['rsu']['manufacturerid']
            beaconIndividualId = initialization_request_jval['initialisationRequest']['rsu']['individualid']
            obeManufacturerId = initialization_response_jval['initialisationResponse']['obeConfiguration']['manufacturerID']

            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (rseTdName, rseManufacturerId, beaconIndividualId, obeManufacturerId, transactionDataFileName, transactionUuid, creation_ts, update_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (rseTdName, rseManufacturerId, beaconIndividualId, obeManufacturerId, transaction_log_filename, transaction_uuid, creation_ts, update_ts))
            conn.commit()

    def update_transaction_metadata(self, transaction_data_filename, metadata_updates):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            values = list(metadata_updates)
            # Filename is used as URI (unique resource id) for the transaction
            values.append(transaction_data_filename)
            update_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
            values.insert(-1, update_ts)
            cursor.execute(f'''
                UPDATE transactions
                SET equOBUId = COALESCE(?, equOBUId),
                    personalAccountNumber = COALESCE(?, personalAccountNumber),
                    lpnCountryCode = COALESCE(?, lpnCountryCode),
                    licencePlateNumber = COALESCE(?, licencePlateNumber),
                    positionLatitude = COALESCE(?, positionLatitude),
                    positionLongitude = COALESCE(?, positionLongitude),
                    authResult = ? OR authResult,
                    update_ts = ?
                WHERE transactionDataFileName = ?
            ''', values)
            conn.commit()

    def get_all_transactions_metadata(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM transactions')
            return cursor.fetchall()

    def get_transactions_metadata_with_limit(self, limit=100):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM transactions LIMIT ?', (limit,))
            return cursor.fetchall()