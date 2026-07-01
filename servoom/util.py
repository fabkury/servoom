"""Small filesystem/text helpers shared by the client and CLI."""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from typing import Any

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """Make ``filename`` safe for Windows/Unix filesystems."""
    sanitized = _INVALID_FILENAME_CHARS.sub("_", filename).strip(". ")
    return sanitized[:max_length]


def safe_console_text(value: Any) -> str:
    """Render ``value`` so it can be printed under the current console encoding."""
    text = "" if value is None else str(value)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        return text.encode(encoding, errors="replace").decode(encoding, errors="replace")
    except Exception:
        return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def convert_epoch_to_local(epoch: int) -> str:
    """Format a Unix timestamp as ``YYYY-MM-DD HH:MM:SS`` in local time."""
    return datetime.fromtimestamp(epoch).strftime("%Y-%m-%d %H:%M:%S")


def append_timestamp(filename: str) -> str:
    """Insert a ``_YYYY-MM-DD_HH-MM-SS`` stamp before the extension."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    stem, ext = os.path.splitext(filename)
    return f"{stem}_{stamp}{ext}"
