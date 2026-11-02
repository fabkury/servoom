"""Tests for ``servoom.audio`` (container sniffing, ADTS header parsing) and
``DivoomClient.download_music``. Synthetic bytes only; the corpus test is skipped when the
local audio set (``corpus/audio/``, git-ignored) is absent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from servoom.audio import AudioContainer, parse_adts, sniff_audio
from servoom.client import DivoomClient

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIO_SET = REPO_ROOT / "corpus" / "audio"


def adts_frame(payload: bytes, *, profile=1, sf_index=4, channels=1, crc_absent=1) -> bytes:
    """One ADTS frame: 7-byte header (no CRC) + payload."""
    length = 7 + len(payload)
    h = bytearray(7)
    h[0] = 0xFF
    h[1] = 0xF0 | crc_absent
    h[2] = (profile << 6) | (sf_index << 2) | (channels >> 2)
    h[3] = ((channels & 0x03) << 6) | (length >> 11)
    h[4] = (length >> 3) & 0xFF
    h[5] = ((length & 0x07) << 5) | 0x1F
    h[6] = 0xFC
    return bytes(h) + payload


def test_sniff_adts_m4a_unknown():
    assert sniff_audio(adts_frame(b"\x00" * 10)) is AudioContainer.ADTS
    assert sniff_audio(b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00") is AudioContainer.M4A
    assert sniff_audio(b"\x00\x00\x00\x18ftypisom\x00\x00\x00\x00") is AudioContainer.MP4
    assert sniff_audio(b"RIFF\x00\x00\x00\x00WAVE") is AudioContainer.UNKNOWN
    assert sniff_audio(b"") is AudioContainer.UNKNOWN
    assert AudioContainer.ADTS.value == "aac" and AudioContainer.M4A.value == "m4a"


def test_parse_adts_counts_frames_and_reads_parameters():
    data = b"".join(adts_frame(bytes([i]) * 20) for i in range(43))  # 43 x 1024 samples, about 1 s
    info = parse_adts(data)
    assert info is not None
    assert (info.profile, info.sample_rate, info.channels, info.crc_protected) == ("LC", 44100, 1, False)
    assert info.frames == 43 and info.bytes_parsed == len(data)
    assert abs(info.duration - 43 * 1024 / 44100) < 1e-9


def test_parse_adts_stops_at_trailing_garbage_and_rejects_other_containers():
    data = adts_frame(b"\x01" * 5) + b"not adts"
    info = parse_adts(data)
    assert info.frames == 1 and info.bytes_parsed == 12
    assert parse_adts(b"\x00\x00\x00\x18ftypM4A ") is None
    assert parse_adts(b"") is None


class FakeSession:
    def __init__(self, body):
        self.body, self.urls = body, []

    def get(self, url, **kwargs):
        self.urls.append(url)
        body = self.body

        class Resp:
            def raise_for_status(self):
                pass

            def iter_content(self, chunk_size=8192):
                yield body
        return Resp()


@pytest.mark.parametrize("body,ext", [(adts_frame(b"\x00" * 10), "aac"),
                                      (b"\x00\x00\x00\x18ftypM4A \x00\x00\x00\x00", "m4a")])
def test_download_music_names_file_by_container(tmp_path, body, ext):
    c = DivoomClient(email="x@example.com", md5_password="0" * 32)
    c._session = FakeSession(body)
    path = c.download_music({"GalleryId": 42, "MusicFileId": "group1/M00/x"}, str(tmp_path))
    assert path == str(tmp_path / f"42_music.{ext}")
    assert Path(path).read_bytes() == body
    assert c._session.urls == ["https://f.divoom-gz.com/group1/M00/x"]
    assert not list(tmp_path.glob("*.part"))


def test_download_music_without_music_returns_none(tmp_path):
    c = DivoomClient(email="x@example.com", md5_password="0" * 32)
    c._session = FakeSession(b"")
    assert c.download_music({"GalleryId": 1, "MusicFileId": ""}, str(tmp_path)) is None
    assert c._session.urls == []


@pytest.mark.skipif(not (AUDIO_SET / "analysis.json").exists(), reason="local audio set not present")
def test_local_audio_set_matches_ffprobe_facts():
    """Every file of the 2026-11-01 set sniffs as recorded, and ADTS parameters match the analysis."""
    rows = json.loads((AUDIO_SET / "analysis.json").read_text(encoding="utf-8"))
    checked = 0
    for row in rows:
        path = AUDIO_SET / "files" / f"{row['gid']}.music.bin"
        if not path.exists():
            continue
        data = path.read_bytes()
        container = sniff_audio(data)
        if row["format_name"] == "aac":
            assert container is AudioContainer.ADTS
            info = parse_adts(data)
            assert info.bytes_parsed == len(data)
            assert (info.sample_rate, info.channels, info.profile) == (int(row["sample_rate"]), row["channels"], "LC")
            # ffprobe's duration for a raw ADTS stream is a bitrate estimate, often far off;
            # the frame count agrees with a full decode (checked on 2026-11-01), so only the
            # recorded frame count is compared here.
            assert info.frames == row["frames_adts"]
        else:
            assert container is AudioContainer.M4A
        checked += 1
    assert checked > 0
