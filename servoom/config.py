"""Client configuration: network knobs only.

Credentials live in :mod:`servoom.credentials`; endpoint paths in :mod:`servoom.const`;
CSV field mappings in :mod:`servoom.csv_export`. This module is deliberately small.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

USER_AGENT = "Aurabox/3.1.10 (iPad; iOS 14.8; Scale/2.00)"

DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": USER_AGENT,
    "Content-Type": "application/json",
}

# Bitmap flag selecting which artwork sizes the gallery endpoints return (16..256 px).
ALL_FILE_SIZES = 0b111111


@dataclass(frozen=True)
class Settings:
    """Tunable client settings. Immutable; override per-client by constructing a new one."""

    batch_size: int = 40
    max_retries: int = 3
    request_timeout: int = 10
    retry_delay: int = 1  # seconds between retries
    file_size_filter: int = ALL_FILE_SIZES
    respect_hide_flag: bool = True
    headers: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HEADERS))
    output_dir: str = "out"


DEFAULT_SETTINGS = Settings()
