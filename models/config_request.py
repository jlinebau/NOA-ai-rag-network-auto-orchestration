#config_request.py

from pydantic import BaseModel

class ConfigRequest(BaseModel):
    vendor: str
    model: str
    os_version: str
    feature: str
    parameters: str
    device_ip: str
    device_name: str
	
