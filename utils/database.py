#database.py

import sqlite3

def score_feedback(status):
    return {
        "pushed": 3,
        "pending": 2,
        "rejected": 1,
        "error": 0
    }.get(status, 0)

def get_db_connection():
    conn = sqlite3.connect("staging_queue.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_staging_db(db_path="staging_queue.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS staging_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor TEXT,
            model TEXT,
            os_version TEXT,
            feature TEXT,
            parameters TEXT,
            generated_config TEXT,
            status TEXT DEFAULT 'pending',
            device_ip TEXT,
            device_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def init_feedback_db(db_path="staging_queue.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            status TEXT,
            prompt TEXT,
            generated_config TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def store_in_staging_queue(request, generated_config, db_path="staging_queue.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO staging_queue (
            vendor, model, os_version, feature, parameters,
            generated_config, status, device_ip, device_name
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (
        request.vendor, request.model, request.os_version,
        request.feature, request.parameters, generated_config,
        request.device_ip, request.device_name
    ))
    conn.commit()
    conn.close()

def log_feedback(request_id, status, prompt, generated_config, db_path="staging_queue.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO feedback_log (request_id, status, prompt, generated_config)
        VALUES (?, ?, ?, ?)
    """, (request_id, status, prompt, generated_config))
    conn.commit()
    conn.close()