import sqlite3

# Initialize the database
def init_db(db_path="cli_library.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cli_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor TEXT NOT NULL,
            model TEXT,
            os_version TEXT,
            feature TEXT NOT NULL,
            cli_block TEXT NOT NULL,
            source TEXT
        );
    """)
    conn.commit()
    conn.close()

# Add a CLI entry
def add_entry(vendor, model, os_version, feature, cli_block, source=None, db_path="cli_library.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cli_library (vendor, model, os_version, feature, cli_block, source)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (vendor, model, os_version, feature, cli_block, source))
    conn.commit()
    conn.close()

# Query entries by vendor and/or feature
def query_entries(vendor=None, feature=None, db_path="cli_library.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = "SELECT * FROM cli_library WHERE 1=1"
    params = []
    if vendor:
        query += " AND vendor = ?"
        params.append(vendor)
    if feature:
        query += " AND feature = ?"
        params.append(feature)
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()
    return results

# Export all entries to a text file
def export_all(output_file="cli_export.txt", db_path="cli_library.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cli_library")
    rows = cursor.fetchall()
    with open(output_file, "w") as f:
        for row in rows:
            f.write(f"ID: {row[0]}\nVendor: {row[1]}\nModel: {row[2]}\nOS Version: {row[3]}\nFeature: {row[4]}\nCLI Block:\n{row[5]}\nSource: {row[6]}\n{'-'*40}\n")
    conn.close()

# Example usage
if __name__ == "__main__":
    init_db()
    # Example entry
    add_entry(
        vendor="Cisco",
        model="Nexus 9000",
        os_version="9.3(x)",
        feature="VLAN",
        cli_block="vlan 10\n name Users\n exit",
        source="Cisco NX-OS Command Reference"
    )
    print("Sample entry added. Querying VLAN configs:")
    for row in query_entries(feature="VLAN"):
        print(row)