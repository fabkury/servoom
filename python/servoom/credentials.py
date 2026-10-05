"""Lazy credential loading.

Credentials are resolved only when you actually need to talk to the Divoom API — never at
import time. This keeps ``import servoom`` (and all offline decoding) working with no
``credentials.py`` and no environment set up.

Resolution order:

1. explicit arguments passed to :func:`load_credentials`,
2. environment variables ``SERVOOM_EMAIL`` / ``SERVOOM_MD5_PASSWORD``,
3. a ``credentials.py`` on the import path exposing ``CONFIG_EMAIL`` /
   ``CONFIG_MD5_PASSWORD`` (the historical location, git-ignored).
"""

from __future__ import annotations

import hashlib
import os
from typing import NamedTuple, Optional


class Credentials(NamedTuple):
    email: str
    md5_password: str


class CredentialsError(RuntimeError):
    """Raised when Divoom credentials are required but could not be resolved."""


def _md5(password: str) -> str:
    return hashlib.md5(password.encode("utf-8")).hexdigest()


def load_credentials(
    email: Optional[str] = None,
    md5_password: Optional[str] = None,
    password: Optional[str] = None,
) -> Credentials:
    """Resolve ``(email, md5_password)`` or raise :class:`CredentialsError`.

    A plain ``password`` (via arg or the ``SERVOOM_PASSWORD`` env var) is MD5-hashed.
    """
    email = email or os.environ.get("SERVOOM_EMAIL")
    md5_password = md5_password or os.environ.get("SERVOOM_MD5_PASSWORD")
    password = password or os.environ.get("SERVOOM_PASSWORD")

    if not (email and (md5_password or password)):
        # Fall back to the legacy git-ignored credentials.py module.
        try:
            import credentials as _legacy  # type: ignore

            email = email or getattr(_legacy, "CONFIG_EMAIL", None)
            md5_password = md5_password or getattr(_legacy, "CONFIG_MD5_PASSWORD", None)
        except ImportError:
            pass

    if password and not md5_password:
        md5_password = _md5(password)

    if not email or not md5_password:
        raise CredentialsError(
            "Divoom credentials not found. Set SERVOOM_EMAIL and SERVOOM_MD5_PASSWORD "
            "(or SERVOOM_PASSWORD), pass them to DivoomClient(...), or provide a "
            "credentials.py with CONFIG_EMAIL / CONFIG_MD5_PASSWORD."
        )
    return Credentials(email, md5_password)
