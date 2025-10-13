#device.py

import os
import logging
from netmiko import ConnectHandler

logger = logging.getLogger("rag_api")

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

def push_config_to_device(device_ip, username, password, config_lines, vendor, model, device_name):
    device_type = get_device_type(vendor, model)
    logger.info(f"Pushing config to {device_name} ({device_ip})")
    try:
        connection = ConnectHandler(
            device_type=device_type,
            ip=device_ip,
            username=username,
            password=password
        )
        output = connection.send_config_set(config_lines.splitlines())
        connection.disconnect()
        logger.info("Push successful:\n" + output)
        return True
    except Exception as e:
        logger.error(f"Push failed: {e}")
        return False
		
