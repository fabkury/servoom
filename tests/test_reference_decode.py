"""Regression tests: decode every bundled reference asset and assert the result is
byte-for-byte what it was before the refactor.

The expected values live in ``tests/reference_baseline.json`` (frame count, dimensions,
speed and a SHA-256 over all concatenated frame bytes). This is the safety net that lets
the decoders be refactored with confidence: if a change alters any decoded pixel, the
hash moves and the test fails.

Run with:  ``python -m pytest tests``
"""

from __future__ import annotations

import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from servoom.layer_file_decoder import LayerFileDecoder
from servoom.pixel_bean_decoder import PixelBeanDecoder

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = json.loads((Path(__file__).parent / "reference_baseline.json").read_text("utf-8"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode(path: Path) -> dict:
    """Decode a reference asset into the same summary shape as the baseline fixture."""
    with redirect_stdout(io.StringIO()):  # decoders are chatty; keep test output clean
        is_layer = path.read_bytes()[:1] == b"\x27"
        if is_layer:
            layer = LayerFileDecoder.decode_file(str(path))
            frames = b"".join(
                layer.composite_frame(i).tobytes() for i in range(layer.num_frames)
            )
            return {"kind": "layer", "frames": layer.num_frames,
                    "width": layer.width, "height": layer.height, "hash": _sha256(frames)}
        bean = PixelBeanDecoder.decode_file(str(path))
        frames = b"".join(
            bean.frames_data[i].tobytes() for i in range(bean.total_frames)
        )
        return {"kind": "pixel", "frames": bean.total_frames, "speed": bean.speed,
                "width": bean.width, "height": bean.height, "hash": _sha256(frames)}


@pytest.mark.parametrize("rel_path", sorted(BASELINE), ids=lambda p: p.split("/")[-1])
def test_reference_asset_decodes_identically(rel_path: str) -> None:
    expected = BASELINE[rel_path]
    got = _decode(REPO_ROOT / rel_path)
    assert got == expected


def test_baseline_covers_every_reference_dat() -> None:
    """Guard against silently dropping coverage: every bundled .dat must be in the baseline."""
    on_disk = {
        p.relative_to(REPO_ROOT).as_posix()
        for p in (REPO_ROOT / "reference-animations").rglob("*.dat")
    }
    assert on_disk == set(BASELINE)
