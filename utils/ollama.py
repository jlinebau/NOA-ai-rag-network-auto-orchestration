#ollama.py

import requests
import json
import logging
import re
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger("rag_api")

def build_prompt(entries, request):
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
	
	