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
                    rseTdName TEXT NOT NULL,
                    rseManufacturerId INTEGER,
                    beaconIndividualId INTEGER,
                    obeManufacturerId INTEGER,
                    equOBUId INTEGER,
                    personalAccountNumber BLOB,
                    licencePlateNumber BLOB,
                    authResult BOOLEAN DEFAULT FALSE,
                    positionLatitude REAL,
                    positionLongitude REAL,
                    creation_ts TEXT NOT NULL,
                    update_ts TEXT NOT NULL
                )
            ''')
            conn.commit()

    def create_transaction_with_init_data(self, td_name, initialization_request_jval, initialization_response_jval, transaction_log_filename):
        with sqlite3.connect(self.db_path) as conn:
            rseTdName = td_name

            creation_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
            update_ts = creation_ts

            rseManufacturerId = initialization_request_jval['initialisationRequest']['rsu']['manufacturerid']
            beaconIndividualId = initialization_request_jval['initialisationRequest']['rsu']['individualid']
            obeManufacturerId = initialization_response_jval['initialisationResponse']['obeConfiguration']['manufacturerID']

            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions (rseTdName, rseManufacturerId, beaconIndividualId, obeManufacturerId, transactionDataFileName, creation_ts, update_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (rseTdName, rseManufacturerId, beaconIndividualId, obeManufacturerId, transaction_log_filename, creation_ts, update_ts))
            conn.commit()

    def get_all_transactions(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM transactions')
            return cursor.fetchall()

    def get_transactions_with_limit(self, limit=100):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM transactions LIMIT ?', (limit,))
            return cursor.fetchall()