"""Offline tests for the forum / notification methods of ``DivoomClient``.

They stub the HTTP layer and replay the response shapes observed on app.divoom-gz.com
(documented in FORUM_API.md), so no credentials or network are needed.
"""

from __future__ import annotations

import pytest

from servoom.client import DivoomClient
from servoom.config import Settings
from servoom.const import ForumRegion


def _post(fid, tag="2"):
    return {"ForumId": str(fid), "TagID": tag, "Title": f"post {fid}"}


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


def test_forum_posts_dedupes_curated_block_and_passes_region(client):
    # Page 1 = 2 curated entries (repeated later) + chronological list; page 2 = tail.
    client._session = FakeSession({
        "/Forum/GetList": [
            {"ReturnCode": 0, "HeaderNum": "2", "TotalNum": 6,
             "ForumList": [_post(30), _post(20), _post(30), _post(20)]},
            {"ReturnCode": 0, "HeaderNum": 0, "TotalNum": 6,
             "ForumList": [_post(10), _post(5)]},
        ]
    })
    posts = client.fetch_forum_posts(region=ForumRegion.CHINA)
    assert [p["ForumId"] for p in posts] == ["30", "20", "10", "5"]
    path, payload = client._session.calls[0]
    assert path == "/Forum/GetList"
    assert payload == {"Token": 2, "UserId": 1, "RegionId": 86, "StartNum": 1, "EndNum": 4}
    assert client._session.calls[1][1]["StartNum"] == 5


def test_forum_posts_tag_filter_is_sent_and_enforced_client_side(client):
    client._session = FakeSession({
        "/Forum/GetList": [
            {"ReturnCode": 0, "ForumList": [_post(9, "2"), _post(8, "6"), _post(7, "6")]},
        ]
    })
    posts = client.fetch_forum_posts(tag=6, limit=1)
    assert [p["ForumId"] for p in posts] == ["8"]
    assert client._session.calls[0][1]["Tag"] == "6"
    assert client._session.calls[0][1]["RegionId"] == ForumRegion.INTERNATIONAL


def test_forum_comments_uses_comment_list_key_and_string_forum_id(client):
    reply = {"CommentId": "2", "Content": "thanks", "CommentChildList": []}
    client._session = FakeSession({
        "/Forum/GetCommentListV2": [
            {"ReturnCode": 0, "CommentListNum": "2", "CurListNum": 1,
             "CommentList": [{"CommentId": "1", "Content": "gg", "SubNum": "1",
                              "CommentChildList": [reply]}]},
            {"ReturnCode": 0, "CommentListNum": "2", "CurListNum": 0, "CommentList": []},
        ]
    })
    comments = client.fetch_forum_comments(3440)
    assert len(comments) == 1
    assert comments[0]["CommentChildList"] == [reply]
    assert client._session.calls[0][1]["ForumId"] == "3440"


def test_forum_tags_and_ambassador_post(client):
    client._session = FakeSession({
        "/Forum/GetTag": [{"ReturnCode": 0, "TagList": [{"TagValue": "2", "TagName": "Contest"}]}],
        "/Forum/GetForumUrl": [{"ReturnCode": 0, "ForumId": "102", "Title": "PIXEL ART AMBASSADOR"}],
    })
    assert client.fetch_forum_tags() == [{"TagValue": "2", "TagName": "Contest"}]
    assert client.fetch_ambassador_program_post()["ForumId"] == "102"
    assert client._session.calls[1][1] == {"Token": 2, "UserId": 1}


def test_chat_groups_are_flattened_with_classify_name(client):
    client._session = FakeSession({
        "/MessageGroup/GetGroupList": [{
            "ReturnCode": 0,
            "ClassifyList": [
                {"ClassifyName": "# Community:", "GroupList": [{"GroupId": "Chat"}]},
                {"ClassifyName": "# Language：", "GroupList": [{"GroupId": "German"}]},
            ],
        }]
    })
    groups = client.fetch_chat_groups()
    assert [(g["GroupId"], g["ClassifyName"]) for g in groups] == [
        ("Chat", "# Community:"), ("German", "# Language：")]


def test_message_lists_and_counters(client):
    client._session = FakeSession({
        "/Message/GetUnReadCnt": [{"ReturnCode": 0, "LikeUnReadCnt": "3"}],
        "/Message/GetLikeList": [{"ReturnCode": 0, "UnReadCnt": "0", "LikeList": [{"UserId": 7}]},
                                 {"ReturnCode": 0, "LikeList": []}],
    })
    assert client.fetch_unread_counts()["LikeUnReadCnt"] == "3"
    assert client.fetch_like_notifications() == [{"UserId": 7}]


def test_lookup_returns_none_on_error_code(client):
    client._session = FakeSession({"/Forum/GetForumUrl": [{"ReturnCode": 3}]})
    assert client.fetch_ambassador_program_post() is None
