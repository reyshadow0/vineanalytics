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

# ── ClickHouse: capa de agregaciones / serving del dashboard (Fase 2) ──────────
# Alimentada desde StarRocks por clickhouse/populate.py. El dashboard/API leen de
# aquí con fallback a StarRocks (ver serving.py). Puerto HTTP por defecto: 8123.
CLICKHOUSE_HOST    = os.getenv("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT    = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DB      = os.getenv("CLICKHOUSE_DB", "vinanalytics")
CLICKHOUSE_USER    = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASS    = os.getenv("CLICKHOUSE_PASS", "")
# Permite desactivar el serving por ClickHouse sin tocar código (fallback total).
CLICKHOUSE_ENABLED = os.getenv("CLICKHOUSE_ENABLED", "1") not in ("0", "false", "False", "")

CSV_PATH       = "data/winemag-data-130k-v2.csv"
STAGE_DIR      = "stage"
ETL_BATCH_SIZE = 1000
