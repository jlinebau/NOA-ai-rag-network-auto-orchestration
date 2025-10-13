from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import logging
from dotenv import load_dotenv

from models.config_request import ConfigRequest
from utils.database import get_db_connection, init_staging_db, store_in_staging_queue
from utils.device import push_config_to_device
from utils.query import query_entries
from utils.ollama import build_prompt, call_ollama
from auth.authentication import authenticate

# Initialize FastAPI app and templates
app = FastAPI()
templates = Jinja2Templates(directory="templates")
load_dotenv()

# Ensure templates directory exists
os.makedirs("templates", exist_ok=True)

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



# Initialize DB
init_staging_db()
init_feedback_db()



# --- Routes ---

@app.post("/webhook")
def handle_webhook(payload: dict, user: str = Depends(authenticate)):
    logger.info("Received webhook payload:\n%s", payload)
    try:
        device = payload.get("device", {})
        config_request = ConfigRequest(
            vendor=device.get("vendor", "unknown"),
            model=device.get("model", "unknown"),
            os_version=device.get("os_version", "unknown"),
            feature=payload.get("feature", "unknown"),
            parameters=payload.get("parameters", ""),
            device_ip=payload.get("device_ip", ""),
            device_name=payload.get("device_name", "")
        )
        entries = query_entries(
            vendor=config_request.vendor,
            model=config_request.model,
            os_version=config_request.os_version,
            feature=config_request.feature
        )
        if not entries:
            raise HTTPException(status_code=404, detail="No CLI examples found.")
        prompt = build_prompt(entries, config_request)
        generated_config = call_ollama(prompt)
        store_in_staging_queue(config_request, generated_config)
        return {
            "status": "queued",
            "vendor": config_request.vendor,
            "model": config_request.model,
            "feature": config_request.feature,
            "device_ip": config_request.device_ip,
            "device_name": config_request.device_name,
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
        raise HTTPException(status_code=404, detail="No CLI examples found.")
    prompt = build_prompt(entries, request)
    response = call_ollama(prompt)
    return {"generated_config": response}

@app.get("/review", response_class=HTMLResponse)
def review_page(request: Request, user: str = Depends(authenticate)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staging_queue WHERE status = 'pending' ORDER BY created_at DESC")
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return templates.TemplateResponse("review.html", {"request": request, "items": items})

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

@app.post("/approve/{id}")
def approve_request(id: int, user: str = Depends(authenticate)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staging_queue WHERE id = ?", (id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Config request not found.")
    success = push_config_to_device(
        row["device_ip"],
        os.getenv("SSH_USERNAME"),
        os.getenv("SSH_PASSWORD"),
        row["generated_config"],
        row["vendor"],
        row["model"],
        row["device_name"]
    )
    new_status = "pushed" if success else "error"
    cursor.execute("UPDATE staging_queue SET status = ? WHERE id = ?", (new_status, id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/review", status_code=303)

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
    success = push_config_to_deeevice(
        row["device_ip"],
        os.getenv("SSH_USERNAME"),
        os.getenv("SSH_PASSWORD"),
        row["generated_config"],
        row["vendor"],
        row["model"],
        row["device_name"]
    )
    new_status = "pushed" if success else "error"
    cursor.execute("UPDATE staging_queue SET status = ? WHERE id = ?", (new_status, id))
    conn.commit()
    conn.close()
    return RedirectResponse(url="/review", status_code=303)
    
    
@app.get("/all-requests", response_class=HTMLResponse)
def all_requests_page(request: Request, user: str = Depends(authenticate)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM staging_queue ORDER BY created_at DESC")
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return templates.TemplateResponse("all_requests.html", {"request": request, "items": items})