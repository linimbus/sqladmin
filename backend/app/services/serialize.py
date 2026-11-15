from __future__ import annotations

import base64
import json
import math
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID


def serialize_value(value: Any) -> Any:
    """Convert arbitrary driver values into JSON-friendly values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return str(value)
        return value
    if isinstance(value, Decimal):
        try:
            number = float(value)
            return number if math.isfinite(number) else str(value)
        except (ValueError, OverflowError):
            return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat(sep=" ") if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        preview = base64.b64encode(raw[:48]).decode("ascii")
        suffix = "…" if len(raw) > 48 else ""
        return f"<binary {len(raw)} bytes> base64:{preview}{suffix}"
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (dict, list)):
        try:
            json.dumps(value)
            return value
        except (TypeError, ValueError):
            return str(value)
    if isinstance(value, (set, tuple)):
        return [serialize_value(item) for item in value]
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)
