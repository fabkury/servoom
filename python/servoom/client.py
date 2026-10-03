"""High-level Divoom API client: authenticate, list/search, download and decode artwork.

The heavy lifting lives elsewhere — HTTP transport and pagination in :mod:`servoom.http`,
CSV export in :mod:`servoom.csv_export`, decoding in :mod:`servoom.pixel_bean_decoder`.
This class just wires them together with auth.
"""

from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Tuple

from . import csv_export
from .config import DEFAULT_SETTINGS, Settings
from .const import ANONYMOUS_ENDPOINTS, ApiEndpoint, ForumRegion, Server
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
        anonymous: bool = False,
    ):
        """``anonymous=True`` skips credentials and sends no ``Token``/``UserId``; the
        endpoints that answer that way are listed in CLOUD_API.md (and in
        ``servoom.const.ANONYMOUS_ENDPOINTS``); the others are logged as warnings."""
        self.anonymous = anonymous
        if anonymous:
            self._email = self._md5_password = None
        else:
            creds = load_credentials(email, md5_password, password)
            self._email = creds.email
            self._md5_password = creds.md5_password
        self._settings = settings
        self._session = DivoomSession(settings)
        self.token: Optional[str] = None
        self.user_id: Optional[int] = None

    # -- auth ---------------------------------------------------------------
    def login(self) -> bool:
        """Authenticate; return True on success (always False for an anonymous client)."""
        if self.anonymous:
            log.error("Cannot login: client was created with anonymous=True")
            return False
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

    def _auth(self, endpoint: Optional[ApiEndpoint] = None) -> Dict:
        if self.anonymous:
            if endpoint is not None and endpoint not in ANONYMOUS_ENDPOINTS:
                log.warning("%s is not known to work anonymously (see CLOUD_API.md)",
                            endpoint.name)
            return {}
        if not self.is_logged_in():
            raise ValueError("Not logged in! Call login() first.")
        return {"Token": self.token, "UserId": self.user_id}

    def _keep(self, item: Dict) -> bool:
        """Pagination predicate: drop hidden artworks when configured to respect HideFlag."""
        if self._settings.respect_hide_flag and item.get("HideFlag"):
            return False
        return True

    def _list(self, endpoint: ApiEndpoint, payload: Dict, *, limit: Optional[int],
              list_keys=("FileList",),
              keep: Optional[Callable[[Dict], bool]] = None) -> List[Dict]:
        """Run a paginated listing and return all kept items.

        ``keep`` is an extra predicate applied on top of the HideFlag filter.
        """
        extra_keep = keep
        keep_fn = (lambda item: self._keep(item) and extra_keep(item)) if extra_keep else self._keep
        items = list(paginate(
            self._session.post_json,
            endpoint.value,
            {**self._auth(endpoint), **payload},
            batch_size=self._settings.batch_size,
            list_keys=list_keys,
            keep=keep_fn,
            limit=limit,
            on_page=lambda start, total: log.info("  %s: %d collected", endpoint.name, total),
        ))
        log.info("Fetched %d items from %s", len(items), endpoint.name)
        return items

    # -- single artwork -----------------------------------------------------
    def fetch_artwork_info(self, gallery_id: int) -> Optional[Dict]:
        """Fetch artwork metadata by gallery ID (or None on error)."""
        resp = self._session.post_json(
            ApiEndpoint.GET_GALLERY_INFO.value,
            {**self._auth(ApiEndpoint.GET_GALLERY_INFO), "GalleryId": gallery_id}
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

        self.download_file(file_id, output_path)
        pixel_bean.update_from_download(output_path)
        log.info("Downloaded: %s", safe_console_text(os.path.basename(output_path)))
        return output_path

    def download_file(self, file_id: str, output_path: str) -> str:
        """Download any cloud file (an artwork ``FileId`` or a ``LayerFileId``) to ``output_path``.

        No login is required: the file server is public once the id is known.
        """
        try:
            resp = self._session.get(f"https://{Server.FILE.value}/{file_id}", stream=True)
            resp.raise_for_status()
            with open(output_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        fh.write(chunk)
        except Exception as exc:
            raise RuntimeError(f"Failed to download file: {exc}") from exc
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
        """List uploads by ``target_user_id`` (``ShowAllFlag`` only matters to moderators).

        Filters go in ``extra``: ``FileSort`` (:class:`~servoom.const.GallerySort`),
        ``FileSize`` (:class:`~servoom.const.GallerySize`), ``FileType``, ``Classify``.
        """
        return self._list(ApiEndpoint.GET_SOMEONE_LIST, {
            "Version": 99, "ShowAllFlag": 1, "SomeOneUserId": target_user_id,
            "FileSize": self._settings.file_size_filter, "RefreshIndex": 0, "FileSort": 0,
            **extra,
        }, limit=limit)

    def fetch_category_files(self, category_id: int, limit: Optional[int] = None,
                             **extra) -> List[Dict]:
        """List files in a gallery category."""
        return self._list(ApiEndpoint.GET_CATEGORY_FILES,
                          self._filters(Classify=category_id, **extra),
                          limit=limit, list_keys=("FileList", "CategoryFileList"))

    def _filters(self, **extra) -> Dict:
        """The filter block every gallery listing takes (CLOUD_API.md, "Gallery filters").

        ``Version`` is the client level the server filters by: below 18 it hides newer
        artworks (CLOUD_API.md, "The Version field"). 19 is what the app sends.
        """
        return {"Classify": 0, "FileSize": self._settings.file_size_filter, "FileType": 5,
                "FileSort": 0, "Version": 19, "RefreshIndex": 0, **extra}

    def fetch_tag_gallery(self, tag_name: str, limit: Optional[int] = None,
                          **extra) -> List[Dict]:
        """List artworks under a tag (token required)."""
        return self._list(ApiEndpoint.GET_TAG_GALLERY,
                          self._filters(TagName=tag_name, Mode=0, **extra), limit=limit)

    def search_gallery(self, query: str, limit: Optional[int] = None, **extra) -> List[Dict]:
        """Search gallery artworks by keyword.

        The filter block is always sent: without it the server applies a narrow default
        and answers with a handful of items.
        """
        return self._list(ApiEndpoint.SEARCH_GALLERY,
                          self._filters(Keywords=query, KeywordsEn=query, **extra),
                          limit=limit)

    def fetch_likes_for_art(self, gallery_id: int, limit: Optional[int] = None) -> List[Dict]:
        """List users who liked an artwork."""
        return self._list(ApiEndpoint.GET_LIKE_USERS, {"GalleryId": gallery_id},
                          limit=limit, list_keys=("UserList",))

    def fetch_comments_for_art(self, gallery_id: int, limit: Optional[int] = None) -> List[Dict]:
        """List top-level comments on an artwork; replies nest under ``CommentChildList``."""
        return self._list(ApiEndpoint.GET_ART_COMMENTS, {"GalleryId": gallery_id},
                          limit=limit, list_keys=("CommentList",))

    # -- forum: the official article feed (FORUM_API.md) ---------------------
    def fetch_forum_tags(self, region: int = ForumRegion.INTERNATIONAL) -> List[Dict]:
        """List forum tags as ``{"TagValue": "2", "TagName": "Contest"}`` records."""
        resp = self._lookup(ApiEndpoint.FORUM_GET_TAG, {"RegionId": int(region)})
        return (resp or {}).get("TagList", [])

    def fetch_forum_posts(self, region: int = ForumRegion.INTERNATIONAL,
                          tag: Optional[int] = None, limit: Optional[int] = None,
                          dedupe: bool = True) -> List[Dict]:
        """List forum posts, newest first.

        Page 1 starts with a curated block (pinned + featured posts) that repeats items
        from the chronological list, so ``dedupe`` drops repeated ``ForumId`` values.
        ``tag`` (a ``TagValue`` from :meth:`fetch_forum_tags`) filters server-side, but the
        curated block ignores the filter, so it is also enforced client-side.
        """
        payload: Dict = {"RegionId": int(region)}
        if tag is not None:
            payload["Tag"] = str(int(tag))
        seen = set()

        def keep(item: Dict) -> bool:
            if tag is not None and str(item.get("TagID")) != str(int(tag)):
                return False
            if dedupe:
                fid = item.get("ForumId")
                if fid in seen:
                    return False
                seen.add(fid)
            return True

        return self._list(ApiEndpoint.FORUM_GET_LIST, payload, limit=limit,
                          list_keys=("ForumList",), keep=keep)

    def fetch_ambassador_program_post(self) -> Optional[Dict]:
        """Fetch the fixed "Pixel Art Ambassador Program" post (``/Forum/GetForumUrl``).

        The endpoint ignores every id parameter and always returns forum post 102, so
        there is no per-id post lookup; use :meth:`fetch_forum_posts` and filter.
        """
        return self._lookup(ApiEndpoint.FORUM_GET_AMBASSADOR_POST, {})

    def fetch_forum_comments(self, forum_id: int, limit: Optional[int] = None,
                             region: int = ForumRegion.INTERNATIONAL) -> List[Dict]:
        """List top-level comments on a forum post, newest first.

        Replies are nested under each comment's ``CommentChildList``; ``limit`` counts
        top-level comments only.
        """
        return self._list(ApiEndpoint.FORUM_GET_COMMENTS,
                          {"RegionId": int(region), "ForumId": str(int(forum_id))},
                          limit=limit, list_keys=("CommentList",))

    # -- notifications and chat-room directory --------------------------------
    def fetch_unread_counts(self) -> Optional[Dict]:
        """Unread like/comment/follower notification counters for the current user."""
        return self._lookup(ApiEndpoint.MESSAGE_GET_UNREAD_CNT, {})

    def fetch_notify_config(self) -> Optional[Dict]:
        """Notification switches (``LikeConfig``/``CommentConfig``/``FansConfig``)."""
        return self._lookup(ApiEndpoint.MESSAGE_GET_NOTIFY_CONFIG, {})

    def fetch_like_notifications(self, limit: Optional[int] = None) -> List[Dict]:
        """Likes received by the current user (the "Message" inbox)."""
        return self._list(ApiEndpoint.MESSAGE_GET_LIKE_LIST, {}, limit=limit,
                          list_keys=("LikeList",))

    def fetch_comment_notifications(self, limit: Optional[int] = None) -> List[Dict]:
        """Comments received by the current user (the "Message" inbox)."""
        return self._list(ApiEndpoint.MESSAGE_GET_COMMENT_LIST, {}, limit=limit,
                          list_keys=("LikeList",))

    def fetch_follower_notifications(self, limit: Optional[int] = None) -> List[Dict]:
        """New followers of the current user (the "Message" inbox)."""
        return self._list(ApiEndpoint.MESSAGE_GET_FANS_LIST, {}, limit=limit,
                          list_keys=("LikeList",))

    def fetch_chat_groups(self) -> List[Dict]:
        """Community chat rooms, flattened; each record carries its ``ClassifyName``.

        Only the directory is served by this API; the messages themselves go through
        the IM provider the app connects to (see FORUM_API.md).
        """
        resp = self._lookup(ApiEndpoint.MESSAGE_GROUP_GET_GROUP_LIST, {})
        groups: List[Dict] = []
        for classify in (resp or {}).get("ClassifyList", []):
            for group in classify.get("GroupList", []):
                groups.append({**group, "ClassifyName": classify.get("ClassifyName", "")})
        return groups

    # -- single-shot lookups ------------------------------------------------
    def _lookup(self, endpoint: ApiEndpoint, payload: Dict) -> Optional[Dict]:
        resp = self._session.post_json(endpoint.value, {**self._auth(endpoint), **payload})
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

    def search_tag(self, query: str, limit: Optional[int] = None, **extra) -> List[Dict]:
        """Search tags by keyword (fuzzy); each hit carries counts and 5 sample artworks.

        ``TagKey=...`` in ``extra`` switches to a prefix match (it takes precedence over
        ``Keywords`` on the server).
        """
        return self._list(ApiEndpoint.SEARCH_TAG, {
            "Keywords": query, "FileSize": self._settings.file_size_filter, "FileSort": 0,
            **extra,
        }, limit=limit, list_keys=("TagList",))

    # -- current account ------------------------------------------------------
    def fetch_my_info(self) -> Optional[Dict]:
        """Full profile of the logged-in account (email, region, level, flags)."""
        return self._lookup(ApiEndpoint.GET_USER_ALL_INFO, {})

    def fetch_my_likes(self, limit: Optional[int] = None, **extra) -> List[Dict]:
        """Artworks the current user liked."""
        return self._list(ApiEndpoint.GET_MY_LIKES, self._filters(**extra), limit=limit)

    def fetch_my_followers(self, limit: Optional[int] = None) -> List[Dict]:
        """Users following the current account (the server only serves one's own list)."""
        return self._list(ApiEndpoint.GET_MY_FOLLOWERS, {}, limit=limit,
                          list_keys=("FollowList",))

    def fetch_my_following(self, limit: Optional[int] = None) -> List[Dict]:
        """Users the current account follows (own list only)."""
        return self._list(ApiEndpoint.GET_MY_FOLLOWING, {}, limit=limit,
                          list_keys=("FollowList",))

    def fetch_blacklist(self, limit: Optional[int] = None) -> List[Dict]:
        """Users blocked by the current account, as ``{"UserId": ...}`` records."""
        return self._list(ApiEndpoint.GET_BLACKLIST, {}, limit=limit,
                          list_keys=("BlackList",))

    def fetch_conversations(self) -> List[Dict]:
        """Private chats of the current user: ``{TargetUserId, Message, SendTime}``."""
        resp = self._lookup(ApiEndpoint.MESSAGE_GET_CONVERSATIONS, {})
        return (resp or {}).get("ConversationList", [])

    def fetch_letters(self, limit: Optional[int] = None) -> List[Dict]:
        """System letters addressed to the current user."""
        return self._list(ApiEndpoint.MESSAGE_GET_LETTERS, {}, limit=limit,
                          list_keys=("LetterList",))

    # -- users (CLOUD_API.md) ---------------------------------------------------
    def fetch_user_score(self, target_user_id: int) -> Optional[Dict]:
        """Score breakdown: ``Score``, ``PixelCnt``, ``AniCnt``, ``RecommendCnt``, ``TopCnt``."""
        return self._lookup(ApiEndpoint.GET_USER_SCORE, {"TargetUserId": target_user_id})

    def fetch_user_medals(self, target_user_id: int, language: str = "en") -> List[Dict]:
        """Every medal the app knows, with ``IsValid``/``ValidTime`` for this user."""
        resp = self._lookup(ApiEndpoint.GET_USER_MEDALS,
                            {"TargetUserId": target_user_id, "Langue": language})
        return (resp or {}).get("MedalList", [])

    def fetch_experts(self, limit: Optional[int] = None, language: str = "en") -> List[Dict]:
        """Ranked artists; each record carries counters and 5 sample artworks in ``FileList``."""
        return self._list(ApiEndpoint.GET_EXPERTS, {
            "Language": language, "FileSize": self._settings.file_size_filter,
            "FileType": 5, "Version": 19, "RefreshIndex": 0,
        }, limit=limit, list_keys=("ExpertList",))

    def fetch_hot_experts(self, **extra) -> List[Dict]:
        """The ten artists featured on the Gallery tab (``ExpertUserId``, ``NickName``, ...)."""
        resp = self._lookup(ApiEndpoint.GET_HOT_EXPERTS, extra)
        return (resp or {}).get("ExpertList", [])

    def fetch_expert_gallery(self, limit: Optional[int] = None) -> List[Dict]:
        """Artworks by ambassador-level artists (a feed the app no longer shows)."""
        return self._list(ApiEndpoint.GET_EXPERT_GALLERY, {}, limit=limit)

    def fetch_tag_users(self, tag_name: str, limit: Optional[int] = None,
                        language: str = "en") -> List[Dict]:
        """Users who post under a tag."""
        return self._list(ApiEndpoint.GET_TAG_USERS,
                          {"TagName": tag_name, "Language": language},
                          limit=limit, list_keys=("UserList",))

    # -- tags and events --------------------------------------------------------
    def suggest_tags(self, prefix: str) -> List[Dict]:
        """Tags starting with ``prefix`` (up to 30), as ``{TagName, GalleryCnt}``."""
        resp = self._lookup(ApiEndpoint.SUGGEST_TAG, {"TagKey": prefix})
        return (resp or {}).get("TagList", [])

    def fetch_hot_tags(self, language: str = "en") -> List[Dict]:
        """The five trending tags shown in the app's search box."""
        resp = self._lookup(ApiEndpoint.GET_HOT_TAGS, {"Language": language})
        return (resp or {}).get("TagList", [])

    def fetch_match_info(self) -> Optional[str]:
        """Name of the running contest (the ``MatchKey`` the Pixel Match category is built on)."""
        resp = self._lookup(ApiEndpoint.GET_MATCH_INFO, {})
        return (resp or {}).get("MatchKey")

    # -- discovery: albums and the Discover tab ---------------------------------
    def fetch_albums(self, limit: Optional[int] = None, **extra) -> List[Dict]:
        """Curated albums, each with counters and 5 sample artworks in ``GalleryList``."""
        return self._list(ApiEndpoint.GET_ALBUMS, {
            "FileSize": self._settings.file_size_filter, "FileSort": 0, **extra,
        }, limit=limit, list_keys=("AlbumList",))

    def fetch_album_info(self, album_id: int, language: str = "en",
                         country: str = "US") -> Optional[Dict]:
        """Album counters plus the ``ForumId`` that hosts its comment thread."""
        return self._lookup(ApiEndpoint.GET_ALBUM_INFO, {
            "AlbumId": album_id, "Langue": language, "CountryISOCode": country})

    def fetch_album_arts(self, album_id: int, limit: Optional[int] = None,
                         **extra) -> List[Dict]:
        """Artworks in an album (same filters as the other listings)."""
        return self._list(ApiEndpoint.GET_ALBUM_ARTS,
                          self._filters(AlbumId=album_id, **extra), limit=limit)

    def fetch_discover_themes(self) -> List[Dict]:
        """The Discover carousel: ``{ForumId, ImageId, Title}`` per contest theme."""
        resp = self._lookup(ApiEndpoint.GET_DISCOVER_THEMES, {})
        return (resp or {}).get("ThemeList", [])

    def fetch_discover_top_new(self) -> Optional[Dict]:
        """The Discover banner: ``NewList`` of two featured posts, ``NewImageId``, ``TextColor``."""
        return self._lookup(ApiEndpoint.GET_DISCOVER_TOP_NEW, {})

    # -- playlists --------------------------------------------------------------
    def fetch_user_playlists(self, target_user_id: int, limit: Optional[int] = None,
                             language: str = "en") -> List[Dict]:
        """Public playlists of a user: ``{PlayId, Name, Describe, CoverFileId, Count, ...}``."""
        return self._list(ApiEndpoint.GET_USER_PLAYLISTS,
                          {"TargetUserId": target_user_id, "Language": language},
                          limit=limit, list_keys=("PlayList",))

    def fetch_my_playlists(self, limit: Optional[int] = None) -> List[Dict]:
        """Playlists of the current account."""
        return self._list(ApiEndpoint.GET_MY_PLAYLISTS, {}, limit=limit,
                          list_keys=("PlayList",))

    def fetch_playlist_arts(self, target_user_id: Optional[int], play_id: int,
                            limit: Optional[int] = None, **extra) -> List[Dict]:
        """Artworks in a playlist (token required); ``target_user_id=None`` reads one of
        the current user's."""
        payload = self._filters(PlayId=play_id, **extra)
        if target_user_id is None:
            return self._list(ApiEndpoint.GET_MY_PLAYLIST_ARTS, payload, limit=limit)
        return self._list(ApiEndpoint.GET_USER_PLAYLIST_ARTS,
                          {"TargetUserId": target_user_id, **payload}, limit=limit)

    # -- server-side legacy render ----------------------------------------------
    def fetch_legacy_preview(self, gallery_id: Optional[int] = None,
                             file_id: Optional[str] = None) -> Optional[Dict]:
        """Ask the server to decode an artwork into 16x16 RGB frames (no token needed).

        Only the legacy containers are understood (16x16 formats 8/9, and the old 64x64
        animations, which come back downsampled to 16x16); anything else answers with
        ``PicCount 1`` and an empty ``FileData``. Returns ``{FileData: [r, g, b, ...],
        PicCount, Speed, xScreenCount, yScreenCount, FileName}`` or None.
        """
        if gallery_id is None and file_id is None:
            raise ValueError("gallery_id or file_id is required")
        payload = {"GalleryId": gallery_id} if gallery_id is not None else {"FileId": file_id}
        return self._lookup(ApiEndpoint.GET_LEGACY_PREVIEW, payload)

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
