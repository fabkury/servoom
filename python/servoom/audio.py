"""The audio clip an artwork can carry (``MusicFileId``): container detection and ADTS facts.

Divoom stores the clip as uploaded (FILE_FORMATS.md, "Audio files"): the Android app sends a
raw AAC ADTS stream (AAC-LC, 44.1 kHz, mono), the iOS app an M4A (MP4) file. Nothing is
encrypted, so any AAC decoder plays the bytes once the container is known. This module only
sniffs and parses headers; it does not decode audio.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

ADTS_SAMPLE_RATES = (96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050,
                     16000, 12000, 11025, 8000, 7350)
ADTS_PROFILES = {0: "Main", 1: "LC", 2: "SSR", 3: "LTP"}
SAMPLES_PER_AAC_FRAME = 1024


class AudioContainer(str, Enum):
    """What the music file is wrapped in. The value is the usual file extension."""

    ADTS = "aac"      # raw AAC ADTS stream (every Android upload seen)
    M4A = "m4a"       # ISO base media file with an ``M4A `` brand (iOS uploads)
    MP4 = "mp4"       # ISO base media file with another brand (not seen, handled anyway)
    UNKNOWN = "bin"


@dataclass(frozen=True)
class AdtsInfo:
    """Facts read from the ADTS frame headers of a raw AAC stream."""

    profile: str
    sample_rate: int
    channels: int
    crc_protected: bool
    frames: int
    bytes_parsed: int

    @property
    def duration(self) -> float:
        """Seconds of audio, from the frame count (1,024 samples per frame)."""
        return self.frames * SAMPLES_PER_AAC_FRAME / self.sample_rate if self.sample_rate else 0.0


def sniff_audio(data: bytes) -> AudioContainer:
    """Tell an ADTS stream from an MP4-family file by the first bytes."""
    if len(data) >= 12 and data[4:8] == b"ftyp":
        return AudioContainer.M4A if data[8:12] == b"M4A " else AudioContainer.MP4
    if len(data) >= 7 and data[0] == 0xFF and (data[1] & 0xF6) == 0xF0:
        return AudioContainer.ADTS
    return AudioContainer.UNKNOWN


def parse_adts(data: bytes) -> Optional[AdtsInfo]:
    """Walk the ADTS frames of ``data``; None if it does not start with a valid header.

    Stops at the first bad sync word, so ``bytes_parsed`` below ``len(data)`` means the
    stream has trailing bytes that are not ADTS frames.
    """
    if sniff_audio(data) is not AudioContainer.ADTS:
        return None
    pos, frames, first = 0, 0, None
    while pos + 7 <= len(data):
        h = data[pos:pos + 7]
        if not (h[0] == 0xFF and (h[1] & 0xF6) == 0xF0):
            break
        crc_absent = h[1] & 0x01
        profile = (h[2] >> 6) & 0x03
        sf_index = (h[2] >> 2) & 0x0F
        channel_cfg = ((h[2] & 0x01) << 2) | (h[3] >> 6)
        frame_len = ((h[3] & 0x03) << 11) | (h[4] << 3) | (h[5] >> 5)
        if frame_len < 7 or sf_index >= len(ADTS_SAMPLE_RATES):
            break
        if first is None:
            first = (profile, sf_index, channel_cfg, crc_absent)
        frames += 1
        pos += frame_len
    if first is None:
        return None
    profile, sf_index, channel_cfg, crc_absent = first
    return AdtsInfo(profile=ADTS_PROFILES[profile], sample_rate=ADTS_SAMPLE_RATES[sf_index],
                    channels=channel_cfg if channel_cfg != 7 else 8, crc_protected=not crc_absent,
                    frames=frames, bytes_parsed=pos)
