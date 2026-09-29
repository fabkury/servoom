"""Offline tests for the gallery / user / discovery methods of ``DivoomClient``.

They stub the HTTP layer and replay response shapes observed on app.divoom-gz.com
(documented in CLOUD_API.md), so no credentials or network are needed.
"""

from __future__ import annotations

import logging

import pytest

from servoom.client import DivoomClient
from servoom.config import Settings
from servoom.const import ANONYMOUS_ENDPOINTS, ApiEndpoint, GalleryCategory, GallerySize, GallerySort
from servoom.http import paginate


def _art(gid, **extra):
    return {"GalleryId": gid, "FileId": f"group1/{gid}", "FileName": f"art {gid}", **extra}


class FakeSession:
    """Minimal stand-in for DivoomSession: records payloads, serves canned pages."""

    def __init__(self, pages):
        self.pages = pages  # path -> list of responses, served in order
        self.calls = []

    def post_json(self, path, payload=None):
        self.calls.append((path, dict(payload or {})))
        queue = self.pages.get(path, [])
        if not queue:
            return {"ReturnCode": 3, "ReturnMessage": "Request data is incomplete"}
        return queue.pop(0)


@pytest.fixture
def client():
    c = DivoomClient(email="x@example.com", md5_password="0" * 32,
                     settings=Settings(batch_size=4))
    c.user_id, c.token = 1, 2
    return c


@pytest.fixture
def anon():
    return DivoomClient(anonymous=True, settings=Settings(batch_size=4))


# -- pagination against capped windows ----------------------------------------------
def test_paginate_advances_by_items_received_not_batch_size():
    """The server caps a page (30 on GetCategoryFileListV2) and truncates larger windows:
    the next window must start right after the last item received."""
    calls = []

    def post(path, payload):
        calls.append(payload)
        start = payload["StartNum"]
        if start > 9:
            return {"ReturnCode": 0, "FileList": []}
        return {"ReturnCode": 0, "FileList": [_art(start), _art(start + 1), _art(start + 2)]}

    items = list(paginate(post, "/GetCategoryFileListV2", {}, batch_size=40))
    assert [i["GalleryId"] for i in items] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert [(c["StartNum"], c["EndNum"]) for c in calls] == [(1, 40), (4, 43), (7, 46), (10, 49)]


# -- anonymous client ------------------------------------------------------------------
def test_anonymous_client_sends_no_auth_and_cannot_login(anon, caplog):
    anon._session = FakeSession({
        "/GetCategoryFileListV2": [{"ReturnCode": 0, "FileList": [_art(5)]},
                                   {"ReturnCode": 0, "FileList": []}],
        "/Tag/GetTagInfo": [{"ReturnCode": 0, "GalleryCnt": 3}],
    })
    assert anon.login() is False
    arts = anon.fetch_category_files(GalleryCategory.ANIMAL, FileSort=GallerySort.POPULAR,
                                     FileSize=GallerySize.W64 | GallerySize.W128)
    assert [a["GalleryId"] for a in arts] == [5]
    path, payload = anon._session.calls[0]
    assert path == "/GetCategoryFileListV2"
    assert "Token" not in payload and "UserId" not in payload
    assert payload["Classify"] == 32 and payload["FileSort"] == 1 and payload["FileSize"] == 20
    assert ApiEndpoint.GET_CATEGORY_FILES in ANONYMOUS_ENDPOINTS

    with caplog.at_level(logging.WARNING, logger="servoom"):
        assert anon.fetch_tag_info("cat") == {"ReturnCode": 0, "GalleryCnt": 3}
    assert any("GET_TAG_INFO" in r.getMessage() for r in caplog.records)


def test_logged_in_client_still_requires_token(client):
    client.token = None
    with pytest.raises(ValueError):
        client.fetch_category_files(0)


# -- listings and their list keys ------------------------------------------------------
def test_someone_arts_uses_v3_and_passes_filters(client):
    client._session = FakeSession({
        "/GetSomeoneListV3": [{"ReturnCode": 0, "FileListNum": 10000, "CurListNum": 2,
                               "FileList": [_art(1), _art(2, HideFlag=1)]},
                              {"ReturnCode": 0, "FileList": []}],
    })
    arts = client.fetch_someone_arts(400343116, FileSort=GallerySort.POPULAR)
    assert [a["GalleryId"] for a in arts] == [1]  # HideFlag respected by default
    payload = client._session.calls[0][1]
    assert payload["SomeOneUserId"] == 400343116
    assert payload["FileSort"] == GallerySort.POPULAR
    assert (payload["StartNum"], payload["EndNum"]) == (1, 4)


def test_experts_albums_and_playlists_use_their_list_keys(client):
    client._session = FakeSession({
        "/GetExpertListV4": [{"ReturnCode": 0, "ExpertListNum": 1000,
                              "ExpertList": [{"UserId": 7, "FileList": [_art(1)]}]},
                             {"ReturnCode": 0, "ExpertList": []}],
        "/Discover/GetAlbumListV3": [{"ReturnCode": 0, "AlbumList": [{"AlbumId": 112}]},
                                     {"ReturnCode": 0, "AlbumList": []}],
        "/Discover/GetAlbumImageListV3": [{"ReturnCode": 0, "FileList": [_art(9)]},
                                          {"ReturnCode": 0, "FileList": []}],
        "/Playlist/GetSomeOneList": [{"ReturnCode": 0, "PlayList": [{"PlayId": 190951}]},
                                     {"ReturnCode": 0, "PlayList": []}],
        "/Playlist/GetSomeOneImageList": [{"ReturnCode": 0, "FileList": [_art(3)]},
                                          {"ReturnCode": 0, "FileList": []}],
        "/Playlist/GetMyImageList": [{"ReturnCode": 0, "FileList": [_art(4)]},
                                     {"ReturnCode": 0, "FileList": []}],
    })
    assert client.fetch_experts()[0]["UserId"] == 7
    assert client.fetch_albums() == [{"AlbumId": 112}]
    assert client.fetch_album_arts(112)[0]["GalleryId"] == 9
    assert client._session.calls[-2][1]["AlbumId"] == 112
    assert client.fetch_user_playlists(400803327) == [{"PlayId": 190951}]
    assert client.fetch_playlist_arts(400803327, 190951)[0]["GalleryId"] == 3
    assert client._session.calls[-2][1]["TargetUserId"] == 400803327
    assert client.fetch_playlist_arts(None, 190951)[0]["GalleryId"] == 4
    assert "TargetUserId" not in client._session.calls[-2][1]


def test_own_relationship_lists_and_letters(client):
    client._session = FakeSession({
        "/GetFansListV2": [{"ReturnCode": 0, "FollowListNum": 1, "FollowList": [{"UserId": 3}]},
                           {"ReturnCode": 0, "FollowList": []}],
        "/GetFollowListV2": [{"ReturnCode": 0, "FollowList": []}],
        "/User/GetBlackList": [{"ReturnCode": 0, "BlackList": [{"UserId": 9}]},
                               {"ReturnCode": 0, "BlackList": []}],
        "/GetNewLetterListV2": [{"ReturnCode": 0, "LastIndex": 0, "LetterList": []}],
        "/Message/GetConversationList": [{"ReturnCode": 0, "ConversationList": [{"TargetUserId": 5}]}],
    })
    assert client.fetch_my_followers() == [{"UserId": 3}]
    assert client.fetch_my_following() == []
    assert client.fetch_blacklist() == [{"UserId": 9}]
    assert client.fetch_letters() == []
    assert client.fetch_conversations() == [{"TargetUserId": 5}]


# -- single-shot lookups ---------------------------------------------------------------
def test_user_lookups(client):
    client._session = FakeSession({
        "/LookScore": [{"ReturnCode": 0, "Score": 187467, "AniCnt": 141}],
        "/Medal/GetList": [{"ReturnCode": 0, "MedalValidCnt": 1,
                            "MedalList": [{"MedalId": "10", "IsValid": 1}]}],
        "/Cloud/GetHotExpert": [{"ReturnCode": 0, "ExpertList": [{"ExpertUserId": "1"}]}],
        "/Tag/SearchTagSimple": [{"ReturnCode": 0, "TagList": [{"TagName": "cat", "GalleryCnt": 3}]}],
        "/Cloud/GetHotTag": [{"ReturnCode": 0, "TagList": [{"TagName": "2021", "TagType": "0"}]}],
        "/Cloud/GetMatchInfo": [{"ReturnCode": 0, "MatchKey": "Monster2026"}],
        "/Discover/GetAlbumInfo": [{"ReturnCode": 0, "ForumId": 3434, "LikeCnt": 1}],
        "/Discover/GetTheme": [{"ReturnCode": 0, "ThemeList": [{"ForumId": 3434}]}],
        "/GetUserAllInfo": [{"ReturnCode": 0, "Email": "x@example.com", "RegionId": 0}],
    })
    assert client.fetch_user_score(400343116)["AniCnt"] == 141
    assert client._session.calls[-1][1]["TargetUserId"] == 400343116
    assert client.fetch_user_medals(400343116) == [{"MedalId": "10", "IsValid": 1}]
    assert client._session.calls[-1][1]["Langue"] == "en"
    assert client.fetch_hot_experts() == [{"ExpertUserId": "1"}]
    assert client.suggest_tags("ca") == [{"TagName": "cat", "GalleryCnt": 3}]
    assert client._session.calls[-1][1]["TagKey"] == "ca"
    assert client.fetch_hot_tags()[0]["TagName"] == "2021"
    assert client.fetch_match_info() == "Monster2026"
    assert client.fetch_album_info(112)["ForumId"] == 3434
    assert client.fetch_discover_themes() == [{"ForumId": 3434}]
    assert client.fetch_my_info()["RegionId"] == 0


def test_lookup_error_codes_give_empty_results(client):
    client._session = FakeSession({
        "/Cloud/GetMatchInfo": [{"ReturnCode": 11}],
        "/Medal/GetList": [{"ReturnCode": 1}],
    })
    assert client.fetch_match_info() is None
    assert client.fetch_user_medals(1) == []


def test_legacy_preview_by_gallery_or_file_id(anon):
    frame = [0, 0, 0] * 256
    anon._session = FakeSession({
        "/Cloud/GetFileData": [
            {"ReturnCode": 0, "FileName": "Kirby", "PicCount": 1, "Speed": 0,
             "xScreenCount": 1, "yScreenCount": 1, "FileData": frame},
            {"ReturnCode": 0, "FileName": "", "PicCount": 1, "FileData": []},
        ]
    })
    out = anon.fetch_legacy_preview(gallery_id=9935)
    assert out["PicCount"] == 1 and len(out["FileData"]) == 768
    assert anon._session.calls[0][1] == {"GalleryId": 9935}
    anon.fetch_legacy_preview(file_id="group1/abc")
    assert anon._session.calls[1][1] == {"FileId": "group1/abc"}
    with pytest.raises(ValueError):
        anon.fetch_legacy_preview()
