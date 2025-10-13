#rag_api.py

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi import Depends
from fastapi.templating import Jinja2Templates
from netmiko import ConnectHandler
from tenacity import retry, stop_after_attempt, wait_fixed
import os
from pydantic import BaseModel
import requests
import json
import re
import logging
import sqlite3
import difflib
from dotenv import load_dotenv

# Initialize FastAPI app and templates
app = FastAPI()
templates = Jinja2Templates(directory="templates")
load_dotenv()
security = HTTPBasic()

# Ensure templates directory exists
os.makedirs("templates", exist_ok=True)

# HTML template for /review
review_html = """
<!DOCTYPE html>
<html>
<head>
    <title>NOA Config Review</title>
</head>
<body>
    <h1>Pending Configuration Requests</h1>
    <ul>
    {% for item in items %}
        <li>
            <a href="/review/{{ item['id'] }}">Request #{{ item['id'] }} - {{ item['vendor'] }} {{ item['model'] }} ({{ item['feature'] }})</a>
        </li>
    {% endfor %}
    </ul>
</body>
</html>
"""

# HTML template for /review/{id}
detail_html = """
<!DOCTYPE html>
<html>
<head>
    <title>NOA Config Detail</title>
</head>
<body>
    <h1>Request #{{ item['id'] }}</h1>
    <p><strong>Vendor:</strong> {{ item['vendor'] }}</p>
    <p><strong>Model:</strong> {{ item['model'] }}</p>
    <p><strong>OS Version:</strong> {{ item['os_version'] }}</p>
    <p><strong>Feature:</strong> {{ item['feature'] }}</p>
    <p><strong>Parameters:</strong> {{ item['parameters'] }}</p>
    <p><strong>Status:</strong> {{ item['status'] }}</p>
    <h2>Generated Configuration</h2>
    <pre>{{ item['generated_config'] }}</pre>

    <form action="/approve/{{ item['id'] }}" method="post">
        <button type="submit">Approve</button>
    </form>

    <form action="/reject/{{ item['id'] }}" method="post">
        <button type="submit">Reject</button>
    </form>

    <form action="/push/{{ item['id'] }}" method="post">
        <button type="submit">Push Config</button>
    </form>

    <p><a href="/review">Back to list</a></p>
</body>
</html>
"""

# Save templates to disk
with open("templates/review.html", "w") as f:
    f.write(review_html)

with open("templates/detail.html", "w") as f:
    f.write(detail_html)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("noa.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("rag_api")


class ConfigRequest(BaseModel):
    vendor: str
    model: str
    os_version: str
    feature: str
    parameters: str
    device_ip: str
    device_name: str

# Helper to get DB connection
def get_db_connection():
    conn = sqlite3.connect("staging_queue.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- Step 2: Initialize staging queue DB ---
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

init_staging_db()


def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != "admin" or credentials.password != os.getenv("UI_PASSWORD", "changeme"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return credentials.username



def get_device_type(vendor: str, model: str) -> str:
    vendor = vendor.lower()
    model = model.lower()
    if "catalyst" in model:
        return "cisco_ios"
    elif "nexus" in model:
        return "cisco_nxos"
    elif "aruba" in vendor:
        return "aruba_os"
    elif "fortigate" in vendor:
        return "fortinet"
    elif "hpe" in vendor or "ff5700" in model:
        return "hp_comware"
    else:
        return "autodetect"



def push_config_to_device(device_ip: str, username: str, password: str, config_lines: str, vendor: str, model: str, device_name: str):
    device_type = get_device_type(vendor, model)
    logger.info(f"Preparing to push config to {device_name} ({device_ip})")
    logger.info(f"Vendor: {vendor}, Model: {model}, Device Type: {device_type}")
    logger.info("Configuration lines:")
    for line in config_lines.splitlines():
        logger.info(f"> {line}")
    try:
        connection = ConnectHandler(
            device_type=device_type,
            ip=device_ip,
            username=username,
            password=password
        )
        output = connection.send_config_set(config_lines.splitlines())
        connection.disconnect()
        logger.info("Push successful. Device output:")
        logger.info(output)
        return True
    except Exception as e:
        logger.error(f"Push failed: {e}")
        return False



def store_in_staging_queue(request: ConfigRequest, generated_config: str, db_path="staging_queue.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO staging_queue (vendor, model, os_version, feature, parameters, generated_config, status, device_ip, device_name)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
    """, (
        request.vendor,
        request.model,
        request.os_version,
        request.feature,
        request.parameters,
        generated_config,
        request.device_ip,
        request.device_name
    ))
    conn.commit()
    conn.close()

@app.post("/webhook")
def handle_webhook(payload: dict, user: str = Depends(authenticate)):
    logger.info("Received webhook payload:\n%s", json.dumps(payload, indent=2))

    try:
        device = payload.get("device", {})
        vendor = device.get("vendor", "unknown")
        model = device.get("model", "unknown")
        os_version = device.get("os_version", "unknown")
        feature = payload.get("feature", "unknown")
        parameters = payload.get("parameters", "")
        device_ip = payload.get("device_ip", "")
        device_name = payload.get("device_name", "")

        config_request = ConfigRequest(
            vendor=vendor,
            model=model,
            os_version=os_version,
            feature=feature,
            parameters=parameters,
            device_ip=device_ip,
            device_name=device_name
        )

        entries = query_entries(
            vendor=config_request.vendor,
            model=config_request.model,
            os_version=config_request.os_version,
            feature=config_request.feature
        )
        if not entries:
            raise HTTPException(status_code=404, detail="No CLI examples found for the given vendor and feature.")

        prompt = build_prompt(entries, config_request)
        generated_config = call_ollama(prompt)

        store_in_staging_queue(config_request, generated_config)

        return {
            "status": "queued",
            "vendor": vendor,
            "model": model,
            "feature": feature,
            "device_ip": device_ip,
            "device_name": device_name,
            "generated_config": generated_config
        }

    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed.")

@app.post("/generate-config")
def generate_config(request: ConfigRequest, user: str = Depends(authenticate)):
    entries = query_entries(
        vendor=request.vendor,
        model=request.model,
        os_version=request.os_version,
        feature=request.feature
    )
    if not entries:
        raise HTTPException(status_code=404, detail="No CLI examples found for the given vendor and feature.")
    prompt = build_prompt(entries, request)
    response = call_ollama(prompt)
    return {"generated_config": response}
	
def normalize(text: str) -> str:
    return text.strip().lower()

def query_entries(vendor: str, model: str, os_version: str, feature: str, db_path="cli_library.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    vendor = normalize(vendor)
    model = normalize(model)
    os_version = normalize(os_version)
    feature_input = feature.strip().lower()

    logger.info(f"Querying CLI examples for vendor='{vendor}', model='{model}', os_version='{os_version}', feature='{feature_input}'")

    cursor.execute("""
        SELECT * FROM cli_library
        WHERE lower(vendor) = ? AND lower(model) = ? AND lower(os_version) = ? AND lower(feature) = ?
    """, (vendor, model, os_version, feature_input))
    results = cursor.fetchall()

    if not results:
        cursor.execute("SELECT DISTINCT vendor FROM cli_library")
        vendors = [row[0].lower() for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT model FROM cli_library")
        models = [row[0].lower() for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT os_version FROM cli_library")
        os_versions = [row[0].lower() for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT feature FROM cli_library")
        features = [row[0] for row in cursor.fetchall()]

        logger.info(f"Available vendors: {vendors}")
        logger.info(f"Available models: {models}")
        logger.info(f"Available OS versions: {os_versions}")
        logger.info(f"Available features: {features}")

        best_vendor = difflib.get_close_matches(vendor, vendors, n=1)
        best_model = difflib.get_close_matches(model, models, n=1)
        best_os_version = difflib.get_close_matches(os_version, os_versions, n=1)

        feature_map = {f: f.split('_')[-1].lower() for f in features}
        stripped_features = list(feature_map.values())
        best_feature_match = difflib.get_close_matches(feature_input, stripped_features, n=1)

        best_feature = []
        if best_feature_match:
            for full, stripped in feature_map.items():
                if stripped == best_feature_match[0]:
                    best_feature = [full]
                    break

        logger.info("Fuzzy match candidates:")
        logger.info(f"Vendor match: {best_vendor}")
        logger.info(f"Model match: {best_model}")
        logger.info(f"OS version match: {best_os_version}")
        logger.info(f"Feature match: {best_feature}")

        if best_vendor and best_model and best_os_version and best_feature:
            fuzzy_vendor = best_vendor[0]
            fuzzy_model = best_model[0]
            fuzzy_os_version = best_os_version[0]
            fuzzy_feature = best_feature[0]

            cursor.execute("""
                SELECT * FROM cli_library
                WHERE lower(vendor) = ? AND lower(model) = ? AND lower(os_version) = ? AND feature = ?
            """, (fuzzy_vendor, fuzzy_model, fuzzy_os_version, fuzzy_feature))
            results = cursor.fetchall()

        if not results and best_vendor and best_feature:
            fuzzy_vendor = best_vendor[0]
            fuzzy_feature = best_feature[0]
            cursor.execute("""
                SELECT * FROM cli_library
                WHERE lower(vendor) = ? AND feature LIKE ?
            """, (fuzzy_vendor, f"%{fuzzy_feature}%"))
            results = cursor.fetchall()

        if not results and best_feature:
            fuzzy_feature = best_feature[0]
            cursor.execute("""
                SELECT * FROM cli_library
                WHERE feature LIKE ?
            """, (f"%{fuzzy_feature}%",))
            results = cursor.fetchall()

    conn.close()
    return results

def build_prompt(entries, request: ConfigRequest):
    examples = "\n\n".join([entry[5] for entry in entries])
    prompt = f"""You are a network assistant. Based on the following CLI examples:

{examples}

Generate a configuration for:
- Vendor: {request.vendor}
- Model: {request.model}
- OS Version: {request.os_version}
- Feature: {request.feature}
- Parameters: {request.parameters}

Respond only with the CLI configuration block using triple backticks.
"""
    logger.info("Generated Prompt:\n%s", prompt)
    return prompt

def extract_cli_block(text):
    match = re.search(r"```(?:bash)?\n(.*?)```", text, re.DOTALL)
    if not match:
        match = re.search(r"```(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def call_ollama(prompt):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "mistral", "prompt": prompt},
            stream=True,
            timeout=60
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Ollama request failed: {e}")
        return "Error: Unable to reach Ollama."

    full_response = ""
    for line in response.iter_lines():
        if line:
            try:
                obj = json.loads(line.decode("utf-8"))
                if "response" in obj:
                    full_response += obj["response"]
            except json.JSONDecodeError:
                continue

    logger.info("Full Ollama Response:\n%s", full_response)
    return extract_cli_block(full_response) if full_response else "No response generated."
	
# /review - list all pending configs
@app.get("/review", response_class=HTMLResponse)
def review_page(request: Request, user: str = Depends(authenticate)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staging_queue WHERE status = 'pending' ORDER BY created_at DESC")
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return templates.TemplateResponse("review.html", {"request": request, "items": items})

# /review/{id} - view config details
@app.get("/review/{id}", response_class=HTMLResponse)
def review_detail(id: int, request: Request, user: str = Depends(authenticate)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staging_queue WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Request not found")
    item = dict(row)
    return templates.TemplateResponse("detail.html", {"request": request, "item": item})

# /approve/{id} - mark as approved


@app.post("/approve/{id}")
def approve_request(id: int, user: str = Depends(authenticate)):
    conn = sqlite3.connect("staging_queue.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM staging_queue WHERE id = ?", (id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Config request not found.")

    config_text = row["generated_config"]
    device_ip = row["device_ip"]
    device_name = row["device_name"]
    vendor = row["vendor"]
    model = row["model"]
    username = os.getenv("SSH_USERNAME")
    password = os.getenv("SSH_PASSWORD")

    success = push_config_to_device(device_ip, username, password, config_text, vendor, model, device_name)

    if success:
        cursor.execute("UPDATE staging_queue SET status = 'pushed' WHERE id = ?", (id,))
    else:
        cursor.execute("UPDATE staging_queue SET status = 'error' WHERE id = ?", (id,))

    conn.commit()
    conn.close()

    return RedirectResponse(url="/review", status_code=303)



# /reject/{id} - mark as rejected
@app.post("/reject/{id}")
def reject_request(id: int, user: str = Depends(authenticate)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE staging_queue SET status = 'rejected' WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/review", status_code=303)
    

@app.post("/push/{id}")
def push_config(id: int, user: str = Depends(authenticate)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staging_queue WHERE id = ?", (id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Config request not found.")

    config_text = row["generated_config"]
    vendor = row["vendor"]
    model = row["model"]
    device_ip = row["device_ip"]
    device_name = row["device_name"]
    username = os.getenv("SSH_USERNAME")
    password = os.getenv("SSH_PASSWORD")

    logger.info(f"{user} is initiating push for request #{id}")
    logger.info(f"Target device: {device_name} ({device_ip})")

    success = push_config_to_device(device_ip, username, password, config_text, vendor, model, device_name)

    new_status = "pushed" if success else "error"
    cursor.execute("UPDATE staging_queue SET status = ? WHERE id = ?", (new_status, id))
    conn.commit()
    conn.close()

    logger.info(f"Push status for request #{id}: {new_status}")
    return RedirectResponse(url="/review", status_code=303)
    
