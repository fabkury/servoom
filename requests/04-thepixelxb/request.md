# Request 04 — Offline archive for ThePixelXḃ_ (2026-11-04)

The artist ThePixelXḃ_ (UserId 400791502) cannot use the download tool at
servoom.pages.dev/download/ because their Divoom account does not log in with email and
password. This request builds them an offline package of every upload with layer files,
likes and comments.

* `fetch.py` — first pass: the 20 newest uploads, decoded to WebP (+ layer PSD).
* `collect.py` — every upload (1,348 on 2026-11-04): artwork file, layer file, sound clip,
  full liker lists and threaded comments. Resumable; paced to 30 API calls per minute;
  tolerates files the server no longer has (404) and the like-list depth cap (3,000).
* `build.py` — decodes to WebP + GIF (+ PSD per layer file), writes per-artwork
  `likes.csv`/`comments.txt`, top-level CSVs, an offline `index.html` gallery and a
  bilingual README; `--zip` packs it.

Only the scripts are tracked. The data (`package/`, logs, the zip) is another user's work
and stays local.

Findings worth keeping: 261 layer files and 9 sound clips from 2021–2023 are gone from the
file host; 305 layer files use an older container (first byte `0x1D`) that servoom does not
decode yet; like counters include deleted accounts, and like lists stop at 3,000 entries.
