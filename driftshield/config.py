"""Configuration management with environment variables."""

import os
from typing import Tuple
from dotenv import load_dotenv


# Load .env file (override=True ensures .env values take precedence over system env vars)
load_dotenv(override=True)


# Base URL for API
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


# Header name to environment variable mapping
_HEADER_ENV_MAP = {
    "X-Tenant-Token": "TENANT_TOKEN",
}


def get_header_value(header_name: str) -> Tuple[str, str] | None:
    """
    Get header value from configuration.
    
    Args:
        header_name: HTTP header name
        
    Returns:
        Tuple of (value, "config") if found in config, None otherwise
    """
    env_var = _HEADER_ENV_MAP.get(header_name)
    if env_var is None:
        return None
    
    value = os.getenv(env_var)
    if value is None:
        return None
    
    return (value, "config")
