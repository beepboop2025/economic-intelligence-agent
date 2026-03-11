"""
Utility functions for Economic Intelligence Agent
Formatting, logging, JSON extraction, and common helpers
"""

import re
import json
import math
import logging
import asyncio
from typing import Any, Dict, Optional, Union
from datetime import datetime


def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """Configure structured logging for the application"""
    log_level = getattr(logging, level.upper(), logging.INFO)

    fmt = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers = [logging.StreamHandler()]

    if log_file:
        import os
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(level=log_level, format=fmt, datefmt=datefmt, handlers=handlers, force=True)

    return logging.getLogger("econ_agent")


def format_number(value: Optional[Union[int, float]], decimals: int = 1) -> str:
    """Format number with dynamic K/M/B/T suffix

    Examples:
        format_number(1500) -> '1.5K'
        format_number(2500000000) -> '2.5B'
        format_number(None) -> 'N/A'
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"

    value = float(value)
    if value == 0:
        return "0"

    abs_val = abs(value)
    sign = "-" if value < 0 else ""

    if abs_val >= 1e12:
        return f"{sign}{abs_val / 1e12:.{decimals}f}T"
    elif abs_val >= 1e9:
        return f"{sign}{abs_val / 1e9:.{decimals}f}B"
    elif abs_val >= 1e6:
        return f"{sign}{abs_val / 1e6:.{decimals}f}M"
    elif abs_val >= 1e3:
        return f"{sign}{abs_val / 1e3:.{decimals}f}K"
    else:
        return f"{sign}{abs_val:.{decimals}f}"


def format_price(value: Optional[float], prefix: str = "$") -> str:
    """Format price with appropriate decimal places"""
    if value is None:
        return "N/A"
    value = float(value) if not isinstance(value, (int, float)) else value
    if value == 0:
        return f"{prefix}0.00"

    abs_val = abs(value)
    if abs_val >= 1000:
        return f"{prefix}{value:,.2f}"
    elif abs_val >= 1:
        return f"{prefix}{value:.2f}"
    elif abs_val >= 0.01:
        return f"{prefix}{value:.4f}"
    else:
        return f"{prefix}{value:.6f}"


def format_percent(value: Optional[float], decimals: int = 2) -> str:
    """Format percentage with sign"""
    if value is None:
        return "N/A"
    if isinstance(value, str) and not value.replace('.', '', 1).replace('-', '', 1).isdigit():
        return "N/A"
    value = Number(value) if not isinstance(value, (int, float)) else value
    return f"{value:+.{decimals}f}%"


def Number(v) -> float:
    """Safe number conversion — returns 0.0 for None/NaN/invalid"""
    if v is None:
        return 0.0
    try:
        result = float(v)
        return 0.0 if math.isnan(result) else result
    except (ValueError, TypeError):
        return 0.0


def extract_json_from_text(text: str) -> Optional[Dict]:
    """Extract JSON object from LLM response text using balanced-brace parser.

    Handles:
    - JSON wrapped in markdown code blocks
    - JSON with surrounding text/explanation
    - Nested braces inside strings
    """
    if not text or not isinstance(text, str):
        return None

    # Strip markdown code fences
    cleaned = re.sub(r'```(?:json)?\s*', '', text)
    cleaned = re.sub(r'```\s*$', '', cleaned)

    # Try direct parse first
    try:
        return json.loads(cleaned.strip())
    except (json.JSONDecodeError, ValueError):
        pass

    # Find first '{' and use balanced-brace matching
    start = cleaned.find('{')
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape_next = False
    end = -1

    for i in range(start, len(cleaned)):
        ch = cleaned[i]

        if escape_next:
            escape_next = False
            continue

        if ch == '\\' and in_string:
            escape_next = True
            continue

        if ch == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end = i
                break

    if end < 0:
        return None

    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return None


def safe_get(data: Any, *keys, default: Any = None) -> Any:
    """Safely navigate nested dicts/lists.

    Example: safe_get(data, 'crypto', 'top_coins', 0, 'price', default=0)
    """
    current = data
    for key in keys:
        try:
            if isinstance(current, dict):
                current = current[key]
            elif isinstance(current, (list, tuple)) and isinstance(key, int):
                current = current[key]
            else:
                return default
        except (KeyError, IndexError, TypeError):
            return default
    return current


def timestamp_now() -> str:
    """ISO format timestamp"""
    return datetime.now().isoformat()


def truncate(text: str, max_len: int = 100) -> str:
    """Truncate text with ellipsis"""
    if not text or len(text) <= max_len:
        return text or ""
    return text[:max_len - 3] + "..."
