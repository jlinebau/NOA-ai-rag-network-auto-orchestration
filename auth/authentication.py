#authentication.py


from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import os

security = HTTPBasic()

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != "admin" or credentials.password != os.getenv("UI_PASSWORD", "changeme"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return credentials.username
