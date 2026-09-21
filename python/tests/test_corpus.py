"""Corpus regression test for the Python decoders.

``corpus/baseline.json`` records what the decoders produced for every file in the shared
reference corpus when the baseline was built. This test re-decodes whatever payloads are
present locally (``corpus/files/`` is git-ignored; see ``corpus/README.md``) and asserts
nothing changed. It is skipped when no payload is present, so a fresh clone stays green.

Run with:  ``python -m pytest tests``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS = REPO_ROOT / "corpus"
sys.path.insert(0, str(CORPUS))


def _cases():
    manifest_path = CORPUS / "manifest.json"
    baseline_path = CORPUS / "baseline.json"
    if not manifest_path.exists() or not baseline_path.exists():
        return []
    baseline = json.loads(baseline_path.read_text("utf-8"))
    manifest = json.loads(manifest_path.read_text("utf-8"))
    cases = []
    for entry in manifest["entries"]:
        rel = entry["path"]
        if rel in baseline and (CORPUS / rel).exists():
            cases.append(pytest.param(rel, baseline[rel], id=rel.split("/", 1)[1]))
    return cases


CASES = _cases()


@pytest.mark.skipif(not CASES, reason="corpus payloads not present (python corpus/corpus.py fetch)")
@pytest.mark.parametrize("rel_path,expected", CASES)
def test_corpus_file_decodes_identically(rel_path: str, expected: dict) -> None:
    from corpus import decode_summary  # corpus/corpus.py

    assert decode_summary(CORPUS / rel_path) == expected
