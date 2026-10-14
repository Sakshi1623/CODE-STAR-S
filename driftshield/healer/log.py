"""Append-only event logging with secret redaction."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Log file path
LOG_FILE = Path("patch_log.jsonl")


# Keys to redact
_REDACTED_KEYS = {"value", "token", "secret"}


def _redact_dict(obj: Any) -> Any:
    """
    Recursively redact sensitive keys in a dictionary.
    
    Args:
        obj: Object to redact
        
    Returns:
        Redacted copy of object
    """
    if isinstance(obj, dict):
        return {
            k: "<redacted>" if k.lower() in _REDACTED_KEYS else _redact_dict(v)
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [_redact_dict(item) for item in obj]
    else:
        return obj


def log_event(event: dict[str, Any]) -> None:
    """
    Log an event to the append-only log file.
    
    Adds UTC timestamp and redacts sensitive keys.
    
    Args:
        event: Event data to log
    """
    # Add timestamp
    timestamped = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **event
    }
    
    # Redact sensitive keys
    redacted = _redact_dict(timestamped)
    
    # Append to log file
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(redacted) + "\n")


def read_all() -> list[dict[str, Any]]:
    """
    Read all events from the log file.
    
    Returns:
        List of event dictionaries
    """
    if not LOG_FILE.exists():
        return []
    
    events = []
    with LOG_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    
    return events
