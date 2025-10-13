#view_db.py

import sqlite3

conn = sqlite3.connect("cli_library.db")
cursor = conn.cursor()

cursor.execute("SELECT vendor, model, os_version, feature, cli_block FROM cli_library")
rows = cursor.fetchall()

for row in rows:
    vendor, model, os_version, feature, cli_block = row
    print(f"Vendor: {vendor}\nModel: {model}\nOS Version: {os_version}\nFeature: {feature}\nCLI Block:\n{cli_block}\n{'-'*60}\n")

conn.close()