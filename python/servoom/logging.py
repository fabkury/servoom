"""Small logging helper so library code never calls ``print()``.

Library modules use ``log = get_logger(__name__)`` and log at appropriate levels. By
default the library stays silent (a ``NullHandler``); applications opt in to output with
:func:`configure`.
"""

from __future__ import annotations

import logging

_ROOT = "servoom"

logging.getLogger(_ROOT).addHandler(logging.NullHandler())


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the ``servoom`` namespace."""
    if name == "__main__" or not name.startswith(_ROOT):
        name = f"{_ROOT}.{name}"
    return logging.getLogger(name)


def configure(level: int = logging.INFO) -> None:
    """Enable simple console logging for the ``servoom`` namespace (for CLIs/scripts)."""
    logger = logging.getLogger(_ROOT)
    logger.setLevel(level)
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
