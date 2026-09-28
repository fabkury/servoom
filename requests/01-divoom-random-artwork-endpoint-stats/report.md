# Divoom random-sampler endpoints: statistical report

Source: `samples.jsonl`, 1801 requests, sampled from 2026-09-28 16:11:56 to 2026-09-28 16:41:56 local time, one request per second, alternating the two endpoints, logged in as the throwaway test account.


## `/Cloud/GetHotTag`

### Transport

| calls | failed | median ms | p95 ms | max ms |
|---|---|---|---|---|
| 901 | 0 | 77 | 81 | 952 |

### Within a call

Items per call: {5: 901}. Calls containing the same item twice: 0 of 901.

### Pool size

| draws | distinct items | seen once | seen twice | Good-Turing coverage | Chao1 estimate | uniform-model estimate |
|---|---|---|---|---|---|---|
| 4505 | 24 | 0 | 0 | 1.0000 | 24.0 | 24.0 |

Discovery curve (distinct items after n calls):

| calls | 1 | 2 | 3 | 5 | 10 | 20 | 50 | 100 | 200 | 400 | 600 | 800 | 901 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| distinct | 5 | 9 | 11 | 15 | 23 | 24 | 24 | 24 | 24 | 24 | 24 | 24 | 24 |

Last new item appeared in call 14 of 901.

Pool stability: with a uniform draw each item has a 99% chance of showing up within 20 calls. Items first seen later than that: 0; items last seen earlier than that before the end: 1.
Suspicious items: `music` (first call 1, last call 880)
First half vs second half of the run: chi-square = 14.7 on 23 dof, p = 0.905 (large p = same frequencies in both halves).

### Distribution over items

Uniform hypothesis over the 24 observed items: expected 187.7 draws each, observed min 161, median 188, max 207; chi-square = 18.4 on 23 dof, p = 0.739.

Per-item frequencies (sorted by count):

| tag | TagType | count | share | ratio to uniform | first-position share |
|---|---|---|---|---|---|
| `Seagull` | 2 | 207 | 4.595% | 1.10 | 11% |
| `party` | 1 | 207 | 4.595% | 1.10 | 64% |
| `Dog` | 0 | 207 | 4.595% | 1.10 | 43% |
| `weather` | 2 | 203 | 4.506% | 1.08 | 0% |
| `music` | 1 | 202 | 4.484% | 1.08 | 83% |
| `song` | 1 | 199 | 4.417% | 1.06 | 22% |
| `rabbit` | 2 | 193 | 4.284% | 1.03 | 100% |
| `Happy` | 1 | 192 | 4.262% | 1.02 | 0% |
| `Reindeer` | 1 | 191 | 4.240% | 1.02 | 0% |
| `Newyear` | 0 | 190 | 4.218% | 1.01 | 17% |
| `game` | 1 | 190 | 4.218% | 1.01 | 3% |
| `Snow` | 2 | 188 | 4.173% | 1.00 | 2% |
| `Eve` | 0 | 187 | 4.151% | 1.00 | 5% |
| `panda` | 2 | 184 | 4.084% | 0.98 | 11% |
| `cat` | 0 | 184 | 4.084% | 0.98 | 30% |
| `Santa` | 1 | 184 | 4.084% | 0.98 | 0% |
| `(empty)` | 0 | 181 | 4.018% | 0.96 | 0% |
| `2021` | 0 | 180 | 3.996% | 0.96 | 51% |
| `Skeleton` | 1 | 179 | 3.973% | 0.95 | 15% |
| `Snowman` | 2 | 176 | 3.907% | 0.94 | 0% |
| `fruit` | 0 | 174 | 3.862% | 0.93 | 4% |
| `Gingerbread` | 2 | 174 | 3.862% | 0.93 | 0% |
| `Wish` | 0 | 172 | 3.818% | 0.92 | 1% |
| `Holiday` | 2 | 161 | 3.574% | 0.86 | 0% |

TagType among distinct tags: {'0': 8, '1': 8, '2': 8}; among draws: {'0': 1475, '1': 1544, '2': 1486}.

Position-wise TagType mix:

| position | type 0 | type 1 | type 2 |
|---|---|---|---|
| 1 | 284 | 376 | 241 |
| 2 | 448 | 284 | 169 |
| 3 | 326 | 220 | 355 |
| 4 | 178 | 266 | 457 |
| 5 | 239 | 398 | 264 |

Pairwise co-occurrence over the 276 item pairs: expected 32.6 joint appearances per pair, pairs never seen together 0, most frequent pair `Dog` + `Newyear` at 51; chi-square = 253.7 on 275 dof, p = 0.817 (tests that items are drawn independently of each other).

### Order within a call

Unordered item pairs seen together: 276; pairs that appeared in both orders: 0.
Every co-occurring pair kept the same relative order, so the endpoint returns a random subset of a fixed underlying sequence. Inferred sequence (ties broken alphabetically):

`rabbit`, `music`, `party`, `2021`, `Dog`, `cat`, `Newyear`, `song`, `Skeleton`, `panda`, `Seagull`, `Eve`, `fruit`, `game`, `weather`, `Wish`, `Holiday`, `Snow`, `Snowman`, `Gingerbread`, `Santa`, `Reindeer`, `Happy`, `(empty)`

Sequence alphabetical? False.

### Dependence between calls

Mean Jaccard overlap: consecutive calls 0.1262, random call pairs 0.1260; identical consecutive sets: 0. For uniform 5-subsets of 24 items the expected overlap is about 0.1163.

Distinct ordered responses: 895 of 901 calls.


## `/Cloud/GetHotExpert`

### Transport

| calls | failed | median ms | p95 ms | max ms |
|---|---|---|---|---|
| 900 | 0 | 80 | 134 | 1148 |

### Within a call

Items per call: {10: 900}. Calls containing the same item twice: 0 of 900.

### Pool size

| draws | distinct items | seen once | seen twice | Good-Turing coverage | Chao1 estimate | uniform-model estimate |
|---|---|---|---|---|---|---|
| 9000 | 25 | 0 | 0 | 1.0000 | 25.0 | 25.0 |

Discovery curve (distinct items after n calls):

| calls | 1 | 2 | 3 | 5 | 10 | 20 | 50 | 100 | 200 | 400 | 600 | 800 | 900 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| distinct | 10 | 16 | 18 | 23 | 25 | 25 | 25 | 25 | 25 | 25 | 25 | 25 | 25 |

Last new item appeared in call 8 of 900.

Pool stability: with a uniform draw each item has a 99% chance of showing up within 9 calls. Items first seen later than that: 0; items last seen earlier than that before the end: 1.
Suspicious items: `Nick` (first call 4, last call 890)
First half vs second half of the run: chi-square = 10.8 on 24 dof, p = 0.99 (large p = same frequencies in both halves).

### Distribution over items

Uniform hypothesis over the 25 observed items: expected 360.0 draws each, observed min 328, median 359, max 389; chi-square = 13.4 on 24 dof, p = 0.96.

Per-item frequencies (sorted by count):

| user id | nickname | level | country | count | share | ratio to uniform | first-position share |
|---|---|---|---|---|---|---|---|
| 400932243 | aicosma | 23 | JP | 389 | 4.322% | 1.08 | 0% |
| 400452209 | Welby | 14 | US | 381 | 4.233% | 1.06 | 0% |
| 400551241 | Misterfloppy | 24 | DE | 377 | 4.189% | 1.05 | 0% |
| 400553677 | JackerZet 🎨 | 23 | RU | 372 | 4.133% | 1.03 | 0% |
| 400786461 | MrGeko | 23 | US | 372 | 4.133% | 1.03 | 1% |
| 400286165 | AhoSome | 24 | FR | 370 | 4.111% | 1.03 | 2% |
| 400681716 | RiverTrace | 30 | CN | 367 | 4.078% | 1.02 | 25% |
| 400244101 | TeruHD | 23 | US | 366 | 4.067% | 1.02 | 0% |
| 400363449 | Clione_DESU | 23 | JP | 366 | 4.067% | 1.02 | 0% |
| 400424999 | comac | 26 | JP | 366 | 4.067% | 1.02 | 0% |
| 400338405 | mudmams | 26 | JP | 364 | 4.044% | 1.01 | 0% |
| 400654438 | 小灰毛☔ | 20 | CN | 363 | 4.033% | 1.01 | 0% |
| 400373425 | mikachi | 28 | JP | 359 | 3.989% | 1.00 | 7% |
| 400803327 | 1 | 28 | CA | 358 | 3.978% | 0.99 | 0% |
| 400498201 | Nick | 22 | UA | 357 | 3.967% | 0.99 | 15% |
| 400251151 | mimosa_soda | 19 | JP | 357 | 3.967% | 0.99 | 0% |
| 400243387 | PON PON | 26 | JP | 356 | 3.956% | 0.99 | 100% |
| 400343116 | 颐笑了之 | 20 | CN | 356 | 3.956% | 0.99 | 39% |
| 400243495 | shikaku-pixel | 23 | JP | 355 | 3.944% | 0.99 | 3% |
| 400270619 | hattori2000 | 15 | JP | 353 | 3.922% | 0.98 | 0% |
| 400619387 | Dr.shock | 24 | US | 353 | 3.922% | 0.98 | 0% |
| 400352629 | broccolito | 23 | DE | 344 | 3.822% | 0.96 | 1% |
| 400342113 | asaha | 24 | JP | 338 | 3.756% | 0.94 | 62% |
| 400237630 | Sam | 14 | CN | 333 | 3.700% | 0.93 | 0% |
| 400297635 | m7kenji | 15 | JP | 328 | 3.644% | 0.91 | 0% |

Titles among distinct experts: {'Divoom Master Pixel Artist': 12, '': 12, 'Silver': 1}.

Countries among distinct experts: {'JP': 11, 'CN': 4, 'US': 4, 'DE': 2, 'RU': 1, 'FR': 1, 'UA': 1, 'CA': 1}.

Levels: min 14, median 23, max 30.

Pairwise co-occurrence over the 300 item pairs: expected 135.0 joint appearances per pair, pairs never seen together 0, most frequent pair `mudmams` + `JackerZet 🎨` at 164; chi-square = 227.3 on 299 dof, p = 0.999 (tests that items are drawn independently of each other).

### Order within a call

Unordered item pairs seen together: 300; pairs that appeared in both orders: 0.
Every co-occurring pair kept the same relative order, so the endpoint returns a random subset of a fixed underlying sequence. Inferred sequence (ties broken alphabetically):

PON PON (400243387, L26), asaha (400342113, L24), 颐笑了之 (400343116, L20), RiverTrace (400681716, L30), Nick (400498201, L22), mikachi (400373425, L28), shikaku-pixel (400243495, L23), AhoSome (400286165, L24), broccolito (400352629, L23), MrGeko (400786461, L23), TeruHD (400244101, L23), Clione_DESU (400363449, L23), Misterfloppy (400551241, L24), Dr.shock (400619387, L24), comac (400424999, L26), mudmams (400338405, L26), hattori2000 (400270619, L15), m7kenji (400297635, L15), 小灰毛☔ (400654438, L20), JackerZet 🎨 (400553677, L23), 1 (400803327, L28), Welby (400452209, L14), mimosa_soda (400251151, L19), Sam (400237630, L14), aicosma (400932243, L23)

Sequence sorted by user id ascending? False. By level descending? False.

### Dependence between calls

Mean Jaccard overlap: consecutive calls 0.2584, random call pairs 0.2546; identical consecutive sets: 0. For uniform 10-subsets of 25 items the expected overlap is about 0.2500.

Distinct ordered responses: 900 of 900 calls.

