"""High-level Divoom API client: authenticate, list/search, download and decode artwork.

The heavy lifting lives elsewhere — HTTP transport and pagination in :mod:`servoom.http`,
CSV export in :mod:`servoom.csv_export`, decoding in :mod:`servoom.pixel_bean_decoder`.
This class just wires them together with auth.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from . import csv_export
from .config import DEFAULT_SETTINGS, Settings
from .const import ApiEndpoint, Server
from .credentials import load_credentials
from .http import DivoomSession, paginate
from .logging import get_logger
from .pixel_bean import PixelBean, PixelBeanState
from .pixel_bean_decoder import PixelBeanDecoder
from .util import sanitize_filename, safe_console_text

log = get_logger(__name__)


class DivoomClient:
    """Client for the Divoom cloud API. Call :meth:`login` before any fetch/download."""

    def __init__(
        self,
        email: Optional[str] = None,
        md5_password: Optional[str] = None,
        password: Optional[str] = None,
        settings: Settings = DEFAULT_SETTINGS,
    ):
        creds = load_credentials(email, md5_password, password)
        self._email = creds.email
        self._md5_password = creds.md5_password
        self._settings = settings
        self._session = DivoomSession(settings)
        self.token: Optional[str] = None
        self.user_id: Optional[int] = None

    # -- auth ---------------------------------------------------------------
    def login(self) -> bool:
        """Authenticate; return True on success."""
        try:
            resp = self._session.post_json(
                ApiEndpoint.USER_LOGIN.value,
                {"Email": self._email, "Password": self._md5_password},
            )
            self.user_id = resp["UserId"]
            self.token = resp["Token"]
            log.info("Logged in to Divoom API")
            return True
        except Exception as exc:
            log.error("Login failed: %s", exc)
            return False

    def is_logged_in(self) -> bool:
        return self.token is not None and self.user_id is not None

    def _auth(self) -> Dict:
        if not self.is_logged_in():
            raise ValueError("Not logged in! Call login() first.")
        return {"Token": self.token, "UserId": self.user_id}

    def _keep(self, item: Dict) -> bool:
        """Pagination predicate: drop hidden artworks when configured to respect HideFlag."""
        if self._settings.respect_hide_flag and item.get("HideFlag"):
            return False
        return True

    def _list(self, endpoint: ApiEndpoint, payload: Dict, *, limit: Optional[int],
              list_keys=("FileList",)) -> List[Dict]:
        """Run a paginated listing and return all kept items."""
        items = list(paginate(
            self._session.post_json,
            endpoint.value,
            {**self._auth(), **payload},
            batch_size=self._settings.batch_size,
            list_keys=list_keys,
            keep=self._keep,
            limit=limit,
            on_page=lambda start, total: log.info("  %s: %d collected", endpoint.name, total),
        ))
        log.info("Fetched %d items from %s", len(items), endpoint.name)
        return items

    # -- single artwork -----------------------------------------------------
    def fetch_artwork_info(self, gallery_id: int) -> Optional[Dict]:
        """Fetch artwork metadata by gallery ID (or None on error)."""
        resp = self._session.post_json(
            ApiEndpoint.GET_GALLERY_INFO.value, {**self._auth(), "GalleryId": gallery_id}
        )
        if resp.get("ReturnCode", 0) != 0:
            log.error("fetch_artwork_info failed: ReturnCode %s", resp.get("ReturnCode"))
            return None
        resp["GalleryId"] = gallery_id  # not always echoed back
        return resp

    def download_art_by_id(self, gallery_id: int, output_dir: Optional[str] = None
                           ) -> Tuple[PixelBean, str]:
        """Fetch metadata, build a PixelBean, and download its file."""
        metadata = self.fetch_artwork_info(gallery_id)
        if not metadata:
            raise ValueError(f"Failed to fetch metadata for gallery ID {gallery_id}")
        bean = PixelBean(metadata=metadata)
        return bean, self.download_art(bean, output_dir=output_dir)

    def download_art(self, pixel_bean: PixelBean, output_dir: Optional[str] = None) -> str:
        """Download the .dat file for ``pixel_bean`` and advance its state to DOWNLOADED."""
        if pixel_bean.state != PixelBeanState.METADATA_ONLY:
            raise ValueError(
                f"Cannot download: state is {pixel_bean.state.value}, expected METADATA_ONLY"
            )
        file_id = pixel_bean.file_id
        if not file_id:
            raise ValueError("PixelBean missing FileId in metadata")

        output_dir = output_dir or "downloads"
        os.makedirs(output_dir, exist_ok=True)
        name = sanitize_filename(pixel_bean.file_name or f"art_{pixel_bean.gallery_id}")
        output_path = os.path.join(output_dir, f"{pixel_bean.gallery_id}_{name}.dat")

        try:
            resp = self._session.get(f"https://{Server.FILE.value}/{file_id}", stream=True)
            resp.raise_for_status()
            with open(output_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        fh.write(chunk)
        except Exception as exc:
            raise RuntimeError(f"Failed to download file: {exc}") from exc

        pixel_bean.update_from_download(output_path)
        log.info("Downloaded: %s", safe_console_text(os.path.basename(output_path)))
        return output_path

    def decode_art(self, pixel_bean: PixelBean) -> PixelBean:
        """Decode a downloaded file and advance ``pixel_bean`` to COMPLETE."""
        if pixel_bean.state != PixelBeanState.DOWNLOADED:
            raise ValueError(
                f"Cannot decode: state is {pixel_bean.state.value}, expected DOWNLOADED"
            )
        file_path = pixel_bean.file_path
        if not file_path or not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")

        decoded = PixelBeanDecoder.decode_file(file_path)
        if decoded is None:
            raise RuntimeError("Failed to decode file: unsupported format or corrupted file")
        pixel_bean.update_from_decode(
            total_frames=decoded.total_frames,
            speed=decoded.speed,
            row_count=decoded.row_count,
            column_count=decoded.column_count,
            frames_data=decoded.frames_data,
        )
        log.info("Decoded: %s", safe_console_text(os.path.basename(file_path)))
        return pixel_bean

    # -- listings -----------------------------------------------------------
    def fetch_my_arts(self, limit: Optional[int] = None, **extra) -> List[Dict]:
        """List the current user's uploads."""
        return self._list(ApiEndpoint.GET_MY_UPLOADS, {
            "Version": 99, "FileSize": self._settings.file_size_filter,
            "RefreshIndex": 0, "FileSort": 0, **extra,
        }, limit=limit)

    def fetch_someone_arts(self, target_user_id: int, limit: Optional[int] = None,
                           **extra) -> List[Dict]:
        """List uploads by ``target_user_id``."""
        return self._list(ApiEndpoint.GET_SOMEONE_LIST, {
            "Version": 99, "ShowAllFlag": 1, "SomeOneUserId": target_user_id,
            "FileSize": self._settings.file_size_filter, "RefreshIndex": 0, "FileSort": 0,
            **extra,
        }, limit=limit)

    def fetch_category_files(self, category_id: int, limit: Optional[int] = None,
                             **extra) -> List[Dict]:
        """List files in a gallery category."""
        return self._list(ApiEndpoint.GET_CATEGORY_FILES, {
            "Classify": category_id, "FileSize": self._settings.file_size_filter,
            "FileType": 5, "FileSort": 0, "Version": 12, "RefreshIndex": 0, **extra,
        }, limit=limit, list_keys=("FileList", "CategoryFileList"))

    def fetch_tag_gallery(self, tag_name: str, limit: Optional[int] = None,
                          **extra) -> List[Dict]:
        """List artworks under a tag."""
        return self._list(ApiEndpoint.GET_TAG_GALLERY, {"TagName": tag_name, **extra},
                          limit=limit)

    def search_gallery(self, query: str, limit: Optional[int] = None, **extra) -> List[Dict]:
        """Search gallery artworks by keyword."""
        return self._list(ApiEndpoint.SEARCH_GALLERY, {"Keywords": query, **extra},
                          limit=limit)

    def fetch_likes_for_art(self, gallery_id: int, limit: Optional[int] = None) -> List[Dict]:
        """List users who liked an artwork."""
        return self._list(ApiEndpoint.GET_LIKE_USERS, {"GalleryId": gallery_id},
                          limit=limit, list_keys=("UserList",))

    # -- single-shot lookups ------------------------------------------------
    def _lookup(self, endpoint: ApiEndpoint, payload: Dict) -> Optional[Dict]:
        resp = self._session.post_json(endpoint.value, {**self._auth(), **payload})
        if resp.get("ReturnCode", 0) != 0:
            log.error("%s failed: ReturnCode %s", endpoint.name, resp.get("ReturnCode"))
            return None
        return resp

    def fetch_someone_info(self, target_user_id: int, **extra) -> Optional[Dict]:
        """Fetch a user's profile."""
        return self._lookup(ApiEndpoint.GET_SOMEONE_INFO,
                            {"SomeOneUserId": target_user_id, **extra})

    def fetch_tag_info(self, tag_name: str, **extra) -> Optional[Dict]:
        """Fetch metadata for a tag."""
        return self._lookup(ApiEndpoint.GET_TAG_INFO, {"TagName": tag_name, **extra})

    def search_user(self, query: str, **extra) -> List[Dict]:
        """Search for users by keyword."""
        resp = self._lookup(ApiEndpoint.SEARCH_USER, {"Keywords": query, **extra})
        return (resp or {}).get("UserList", [])

    def search_tag(self, query: str, **extra) -> List[Dict]:
        """Search for tags by keyword."""
        resp = self._lookup(ApiEndpoint.SEARCH_TAG, {"Keywords": query, **extra})
        return (resp or {}).get("TagList", [])

    # -- bean/download convenience -----------------------------------------
    def fetch_my_arts_as_beans(self, **kwargs) -> List[PixelBean]:
        return [PixelBean(metadata=art) for art in self.fetch_my_arts(**kwargs)]

    def fetch_someone_arts_as_beans(self, target_user_id: int, **kwargs) -> List[PixelBean]:
        return [PixelBean(metadata=a) for a in self.fetch_someone_arts(target_user_id, **kwargs)]

    def download_my_arts(self, output_dir: Optional[str] = None, **kwargs) -> List[str]:
        """Download every upload of the current user."""
        output_dir = output_dir or os.path.join("downloads", "my_arts")
        return self._download_beans(self.fetch_my_arts_as_beans(**kwargs), output_dir)

    def download_someone_arts(self, target_user_id: int, output_dir: Optional[str] = None,
                              **kwargs) -> List[str]:
        """Download every upload of ``target_user_id``."""
        output_dir = output_dir or os.path.join("downloads", str(target_user_id))
        return self._download_beans(
            self.fetch_someone_arts_as_beans(target_user_id, **kwargs), output_dir
        )

    def _download_beans(self, beans: List[PixelBean], output_dir: str) -> List[str]:
        os.makedirs(output_dir, exist_ok=True)
        if not beans:
            log.info("No arts to download")
            return []
        log.info("Downloading %d files to %s", len(beans), output_dir)
        paths = []
        for i, bean in enumerate(beans, 1):
            try:
                paths.append(self.download_art(bean, output_dir=output_dir))
            except Exception as exc:
                log.warning("  [%d/%d] Failed to download %s: %s",
                            i, len(beans), bean.gallery_id or i, exc)
        log.info("Downloaded %d/%d files to %s", len(paths), len(beans), output_dir)
        return paths

    def export_artworks_to_csv(self, beans, base_filename: str = "artworks",
                               output_dir: Optional[str] = None, include_tags: bool = True
                               ) -> Dict[str, str]:
        """Export artwork metadata to CSV (delegates to :mod:`servoom.csv_export`)."""
        return csv_export.export_artworks_to_csv(
            beans, base_filename=base_filename,
            output_dir=output_dir or self._settings.output_dir, include_tags=include_tags,
        )
