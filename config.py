import os

POCKETBASE_URL        = os.getenv("POCKETBASE_URL", "http://127.0.0.1:8090")
POCKETBASE_COLLECTION = "wine_reviews"
POCKETBASE_ADMIN_EMAIL    = "sebastiancastro57@hotmail.com"
POCKETBASE_ADMIN_PASSWORD = "DevilHunter@2004"

STARROCKS_HOST = os.getenv("STARROCKS_HOST", "localhost")
STARROCKS_PORT = 9030
STARROCKS_DB   = "retailytics"
STARROCKS_USER = "root"
STARROCKS_PASS = ""

CSV_PATH       = "data/winemag-data-130k-v2.csv"
STAGE_DIR      = "stage"
ETL_BATCH_SIZE = 1000
