Request 02 — the definitive, community-facing case against the 2,000-account Divoom
like-block, in eight languages. Published at https://servoom.pages.dev/bots/ (since
26 October 2026; `python build_page.py site` writes `docs/public/bots/` here and
`data/bots/` in the sibling servoom-stats checkout, which the site build downloads) and,
earlier, as a private artifact: https://claude.ai/artifact/YSaRPz4o1UuGmW4FQ9pnyr

Files: `request.md`, `questions.md` (intake); `collect_block.py` (avatars + full artwork
lists of the 2,000 accounts, 9 Oct 2026); `stats.py` (numbers.json, decodes old-format
avatars, example pairs); `content_<lang>.json` (page strings; English is the source, the
others were translated from it); `build_page.py` (writes out/like-block.html, or the site area with `site`).
`out/` is git-ignored: it holds third-party avatars, artwork thumbnails and raw listings.
