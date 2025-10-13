#query_db.py
from cli_library import query_entries

results = query_entries(vendor="Cisco", feature="VLAN")
for row in results:
    print(row)
