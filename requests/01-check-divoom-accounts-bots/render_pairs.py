"""Render first frames of the byte-identical bot/original pairs (formats 3, 4, 7 handled
here; others via the servoom decoder, already in out/pairs/). Writes out/pairs_final.json."""
import base64, glob, hashlib, json, zlib
from pathlib import Path
import numpy as np
from PIL import Image
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"; P = OUT / "pairs"
def frame(path):
    d = Path(path).read_bytes(); t = d[0]
    if t == 3: rgb = d[1:769]
    elif t == 4: rgb = d[4:4 + 768]
    elif t == 7: rgb = base64.b64decode(json.loads(zlib.decompress(d[1:]))["previewData"])[:768]
    else: return None
    return Image.fromarray(np.frombuffer(rgb, np.uint8).reshape(16, 16, 3), "RGB")
pairs = json.loads((OUT / "pairs.json").read_text(encoding="utf-8"))
final, seen = [], set()
for p in pairs:
    if not p["same_file"] or p["bot_gid"] in seen: continue
    seen.add(p["bot_gid"])
    row = dict(p)
    for side, gid in (("bot", p["bot_gid"]), ("orig", p["orig_gid"])):
        f = glob.glob(str(OUT / "dl" / f"{gid}_*"))[0]
        row[f"{side}_md5"] = hashlib.md5(Path(f).read_bytes()).hexdigest()
        row[f"{side}_bytes"] = Path(f).stat().st_size
        png = P / f"{gid}.png"
        if not png.exists():
            im = frame(f)
            if im is not None: im.resize((128, 128), Image.NEAREST).save(png)
        row[f"{side}_png"] = png.name if png.exists() else None
    final.append(row)
(OUT / "pairs_final.json").write_text(json.dumps(final, indent=1, ensure_ascii=False), encoding="utf-8")
for r in final: print(r["bot"], r["bot_gid"], r["orig_gid"], r["bot_md5"] == r["orig_md5"], r["bot_png"], r["orig_png"], r["bot_title"])
