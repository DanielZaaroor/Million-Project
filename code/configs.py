import os
import sqlite3
from utils import log

# --- Static Vars
# from the docker-compose environment variables
RABBIT_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
LOG_FILE = "message_log.json"
WUZAPI_HOST = os.getenv("WUZAPI_HOST")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
MILLION_GROUP_JID = os.getenv("MILLION_GROUP_JID")
ADMIN_GROUP_JID = os.getenv("ADMIN_GROUP_JID")
ALERT_GROUP_JID = os.getenv("ALERT_GROUP_JID")
IS_SUSPENDED = False


# --- Database Setup ---
DB_PATH = "/app/data/million_data.db"
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
    

def init_database():
    """Create the tables if it's the first time running"""
    global IS_SUSPENDED

    # Table 1: The Historical Log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS valid_counts (
            number INTEGER PRIMARY KEY,
            sender TEXT,
            push_name TEXT,
            timestamp REAL,
            msg_id TEXT,
            msg_secret TEXT
        )
    """)

    # Migration: Add msg_secret to existing table if it is missing
    cursor.execute("PRAGMA table_info(valid_counts)")
    columns = [column[1] for column in cursor.fetchall()]
    if "msg_secret" not in columns:
        cursor.execute("ALTER TABLE valid_counts ADD COLUMN msg_secret TEXT")

    # Table 2: The Suspension State (single row)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            is_suspended INTEGER DEFAULT 0
        )
    """)

    cursor.execute("INSERT OR IGNORE INTO bot_state (id, is_suspended) VALUES (1, 0)")

    # Table 3: The Mistake window buffer
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pending_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_id TEXT,
            data TEXT
        )
    """)
    conn.commit()

    cursor.execute("SELECT is_suspended FROM bot_state")
    row = cursor.fetchone()
    if row is not None:
        IS_SUSPENDED = bool(row[0])
    log(" [*] Database is ready and memory state loaded")
