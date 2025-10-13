#parse_cli_file.py
   
import sqlite3
import os
import sys

def init_db(db_path="cli_library.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cli_library (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vendor TEXT,
        model TEXT,
        os_version TEXT,
        feature TEXT,
        cli_block TEXT,
        source TEXT
    );
    """)
    conn.commit()
    conn.close()

def entry_exists(vendor, model, os_version, feature, cli_block, db_path="cli_library.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM cli_library
        WHERE vendor = ? AND model = ? AND os_version = ? AND feature = ? AND cli_block = ?
    """, (vendor, model, os_version, feature, cli_block.strip()))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def insert_entry(vendor, model, os_version, feature, cli_block, source, db_path="cli_library.db"):
    if not entry_exists(vendor, model, os_version, feature, cli_block, db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO cli_library (vendor, model, os_version, feature, cli_block, source)
        VALUES (?, ?, ?, ?, ?, ?);
        """, (vendor, model, os_version, feature, cli_block.strip(), source))
        conn.commit()
        conn.close()

def parse_cli_file(file_path):
    source = os.path.basename(file_path)
    filename = source.replace(".cli", "").replace(".txt", "")
    parts = filename.split("_")

    vendor = parts[0].capitalize() if len(parts) > 0 else "Unknown"
    model = parts[1].upper() if len(parts) > 1 else "Unknown"
    os_version = parts[2].upper() if len(parts) > 2 else "Unknown"

    with open(file_path, "r") as f:
        lines = f.readlines()

    current_feature = None
    current_block = []

    for line in lines:
        if line.startswith("###"):
            if current_feature and current_block:
                cli_block = "\n".join(current_block)
                insert_entry(vendor, model, os_version, current_feature, cli_block, source)
            current_block = []
            current_feature = line.strip().replace("###", "").strip()
        else:
            current_block.append(line.rstrip())

    if current_feature and current_block:
        cli_block = "\n".join(current_block)
        insert_entry(vendor, model, os_version, current_feature, cli_block, source)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python parse_cli_file.py <path_to_cli_file>")
        sys.exit(1)

    cli_file_path = sys.argv[1]
    if not os.path.isfile(cli_file_path):
        print(f"Error: File '{cli_file_path}' does not exist.")
        sys.exit(1)

    init_db()
    parse_cli_file(cli_file_path)
    print(f"Parsed and inserted CLI blocks from '{cli_file_path}' into cli_library.db")