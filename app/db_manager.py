import sqlite3
from typing import List, Dict

DB_FILE = "db/gt_ema_cross.db"

def init_database():
    """
    Initialize the database, creating tables if they do not exist.
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    # Table for highly profitable wallets (include coin column)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pool TEXT NOT NULL,
            coin TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()

def save_alert(pool: str, coin: str):
    """
    Save alerts to the database.
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO alerts (pool, coin)
        VALUES (?, ?)
    """, (pool, coin))

    connection.commit()
    connection.close()

def get_alerts():
    """
    Get all alerts from the database.
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM alerts")
    alerts = cursor.fetchall()

    connection.close()

    return alerts

def get_recent_alert(pool_address):
    """
    Fetch the most recent alert for the given pool_address within the past hour.
    """
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    query = """
    SELECT timestamp FROM alerts
    WHERE pool = ?
    ORDER BY timestamp DESC
    LIMIT 1
    """

    cursor.execute(query, (pool_address,))
    result = cursor.fetchone()
    return result[0] if result else None