# Are "Drew" and "julycat" bots? — Yes, both belong to the Divoom like-block

Checked 2026-10-09 with a brand-new read-only account (`TEST_ACCOUNTS["bots_check_01"]`,
UserId 405031725, see `account.md`). No main-account data was used and the new account
never followed, liked, commented or messaged anyone.

## Identification

The screenshots show no UserId and `/SearchUser` is broken, so the accounts were found in
two steps: (1) the like-count sequence of their artwork grids was matched against the
local whole-catalog crawl in servoom-raw, which pointed at accounts inside the known
like-block (even UserIds 400971852–400975850); (2) all 2,000 block profiles were read with
`GetSomeoneInfoV2` and matched by nickname (`scan_block.py`, `out/block_profiles.jsonl`).

| Screenshot | UserId | Level | Score | Likes | Followers | Country | Even id in block |
|---|---:|---:|---:|---:|---:|---|---|
| julycat (IMG_6922) | 400973210 | 10 | 335 | 294 | 38 | UZ | yes |
| Drew (IMG_6924) | 400975304 | 1 | 514 | 350 | 20 | CF | yes |

Every number matches the screenshots exactly, and the artwork titles returned by
`GetSomeoneListV3` match the grids (Drew: 鲸鱼, ミニオン, 猪, 佩琦, cow, Hearts, Pikachu,
Snap...; julycat: music, BL, 平安银行, "Timmy from tpe!" mushroom...).

## Evidence (`out/evidence_<uid>.json`)

1. **Membership in the like-block.** Both UserIds are even numbers inside
   400971852–400975850, the 2,000-account block documented on 2026-10-04 that produces
   roughly two thirds of all likes on Divoom. No odd id exists in that range; the ids were
   issued as a reserved batch.
2. **Cloned portfolios.** Every artwork has an even GalleryId (791358–791382 for julycat,
   812710–812740 for Drew: consecutive even ids, the block's insertion pattern) and a
   2018 upload date. 8 of julycat's 11 and 11 of Drew's 15 artworks carry the exact same
   upload second as an artwork owned by a different, ordinary (non-block) account; the
   rest are originals whose owners are no longer in the public catalog. These are copies of
   other users' 2018 works, not their own.
3. **Industrial liking.** In the servoom-raw like records (crawls of 2026-10-05 to 10-08)
   julycat was seen as the liker of 488 artworks by 283 different owners, Drew of 493 by
   270 owners, each artwork liked once. The block's per-account mean over the same records
   is 483 (std 22, min 417, max 574): both sit in the middle of a perfectly uniform
   distribution, which is how the block spreads its likes. (The timestamps in the records
   are crawl times, so the hour histogram reflects the crawl schedule, not the bot's.)
4. **No human traces.** Follow count 0 for both, 0 comments on all of their artworks,
   `UserNewSign` empty, country codes (Uzbekistan, Central African Republic) drawn from the
   block's random spread over 206 countries, and the same four-to-five standard medal
   images every block account carries.
5. **Inconsistent stats.** Drew is Level 1 with Score 514 while julycat is Level 10 with
   Score 335; level and score are unrelated to activity in the block.

## Verdict

Both are automated accounts of the Divoom like-block (most likely platform-run, as
concluded in the 2026-10-04 study). Likes and follows from them are not real audience
signals.

## Files

- `request.md`, `questions.md` — intake.
- `IMG_6922.webp`, `IMG_6924.webp` — the screenshots.
- `register_account.py` — registered the fresh account and stored it (git-ignored).
- `confirm_candidates.py`, `scan_block.py`, `evidence.py` — the checks.
- `out/` — profiles of all 2,000 block accounts, evidence JSON per account, logs.

Note: `out/` is kept local only (the repo's `.gitignore` excludes every `out/` folder, and
the folder holds 2,000 third-party profiles, which should not be published).
