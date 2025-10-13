#rag_test.py

import sqlite3
import requests

def query_vlan_examples(db_path="cli_library.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT vendor, model, os_version, feature, cli_block FROM cli_library
        WHERE feature = 'VLAN'
    """)
    results = cursor.fetchall()
    conn.close()
    return results

def build_prompt(entries, request_params):
    examples = "\n\n".join([entry[4] for entry in entries])  # cli_block
    prompt = f"""You are a network assistant. Based on the following CLI examples:

{examples}

Generate a configuration for:
- Vendor: {request_params['vendor']}
- Model: {request_params['model']}
- OS Version: {request_params['os_version']}
- Feature: {request_params['feature']}
- Parameters: {request_params['parameters']}
"""
    return prompt

def call_ollama(prompt):
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": "mistral", "prompt": prompt}
    )
    return response.json().get("response", "")

if __name__ == "__main__":
    test_request = {
        "vendor": "Cisco",
        "model": "Catalyst 9200",
        "os_version": "IOS XE",
        "feature": "VLAN",
        "parameters": "Create VLAN 30 named IoT with IP address 192.168.30.1/24"
    }

    vlan_entries = query_vlan_examples()
    if vlan_entries:
        prompt = build_prompt(vlan_entries, test_request)
        print("Generated Prompt:\n", prompt)
        print("\nCalling Mistral via Ollama...\n")
        response = call_ollama(prompt)
        print("Mistral Response:\n", response)
    else:
        print("No VLAN entries found in the database.")