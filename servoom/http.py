"""HTTP transport and pagination for the Divoom API.

Two things live here so the client doesn't have to repeat them a dozen times:

* :class:`DivoomSession` — one place that builds URLs, sets headers/timeout, retries on
  transient network errors, and parses JSON.
* :func:`paginate` — the single ``StartNum``/``EndNum`` loop every listing endpoint uses.
"""

from __future__ import annotations

import time
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Sequence

import requests

from .config import DEFAULT_SETTINGS, Settings
from .const import Server
from .logging import get_logger

log = get_logger(__name__)


class DivoomSession:
    """Thin wrapper over ``requests.Session`` for the Divoom JSON API."""

    def __init__(self, settings: Settings = DEFAULT_SETTINGS):
        self._settings = settings
        self._session = requests.Session()
        self._session.headers.update(settings.headers)

    @staticmethod
    def url(path: str, server: Server = Server.API) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"https://{server.value}{path}"

    def post_json(self, path: str, payload: Optional[Dict] = None) -> Dict:
        """POST ``payload`` as JSON and return the parsed response.

        Retries on transient transport errors (``settings.max_retries``). Raises
        ``requests.RequestException`` if every attempt fails, or ``ValueError`` if the
        final response body is not JSON.
        """
        url = self.url(path)
        last_exc: Optional[Exception] = None
        for attempt in range(self._settings.max_retries):
            try:
                resp = self._session.post(
                    url, json=payload or {}, timeout=self._settings.request_timeout
                )
                return resp.json()
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self._settings.max_retries - 1:
                    time.sleep(self._settings.retry_delay)
        raise last_exc  # type: ignore[misc]

    def get(self, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self._settings.request_timeout)
        return self._session.get(url, **kwargs)


def _first_nonempty_list(data: Dict, keys: Sequence[str]) -> List[Dict]:
    for key in keys:
        value = data.get(key)
        if value:
            return value
    return []


def paginate(
    post: Callable[[str, Dict], Dict],
    path: str,
    base_payload: Dict,
    *,
    batch_size: int,
    list_keys: Sequence[str] = ("FileList",),
    keep: Optional[Callable[[Dict], bool]] = None,
    limit: Optional[int] = None,
    on_page: Optional[Callable[[int, int], None]] = None,
) -> Iterator[Dict]:
    """Yield items across paginated ``StartNum``/``EndNum`` requests.

    Args:
        post: callable like :meth:`DivoomSession.post_json`.
        path: endpoint path.
        base_payload: fields common to every page (auth, filters, keywords, ...).
        batch_size: window size per request.
        list_keys: response keys to read the item list from (first non-empty wins).
        keep: predicate; items for which it returns ``False`` are skipped.
        limit: stop after yielding this many items (``None`` = no limit).
        on_page: optional ``(start, running_total)`` progress callback.

    Stops on: an error ``ReturnCode``, a page with no items, a non-JSON body, or ``limit``.
    """
    keep = keep or (lambda _item: True)
    start = 1
    collected = 0
    while True:
        payload = {**base_payload, "StartNum": start, "EndNum": start + batch_size - 1}
        try:
            data = post(path, payload)
        except ValueError:
            log.warning("Non-JSON response for %s at StartNum=%d", path, start)
            return
        if data.get("ReturnCode", 0) != 0:
            log.debug("Stopping %s: ReturnCode=%s", path, data.get("ReturnCode"))
            return
        items = _first_nonempty_list(data, list_keys)
        if not items:
            return
        for item in items:
            if not keep(item):
                continue
            yield item
            collected += 1
            if limit is not None and collected >= limit:
                return
        if on_page:
            on_page(start, collected)
        start += batch_size


def collect(items: Iterable[Dict]) -> List[Dict]:
    """Materialize a paginate() generator into a list."""
    return list(items)
