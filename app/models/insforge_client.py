import requests
import json
import logging
from app.core.config import settings
from datetime import datetime

logger = logging.getLogger(__name__)

# Fetch project metadata to construct the URL dynamically
with open(".insforge/project.json", "r") as f:
    project_config = json.load(f)
    
INSFORGE_URL = f"{project_config['oss_host']}/api/database/advance/rawsql"
API_KEY = project_config['api_key']

def execute_sql(query, params=None):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {"query": query}
    if params:
        payload["params"] = params
        
    try:
        resp = requests.post(INSFORGE_URL, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json().get('rows', [])
    except Exception as e:
        logger.error(f"SQL execution failed: {query} with error {e}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Response: {e.response.text}")
        raise e
