"""Turn BigQuery output into pairs.json for Geopolitica.
  python3 mkpairs.py all_pairs_output.json                 (output of all_pairs.sql)
  python3 mkpairs.py old_weekly.json --weekly AFG PAK      (older single-pair weekly file)
Writes pairs.json: { "_w": "<Monday after the last full week>", "_war": { "RUS-UKR": [last 4 weeks, 4 weeks before] }, "AFG-PAK": [[period, type, initiator, events, toneSum, conflict], ...] }
Initiator 0 is the alphabetically first code of the pair."""
import json, sys, os, datetime
ALIAS = {"ROM": "ROU", "TMP": "TLS", "ZAR": "COD", "PSE": "PSX", "GZS": "PSX", "WSB": "PSX", "KSV": "KOS", "SSD": "SDS", "ESH": "SAH"}
args = [x for x in sys.argv[1:] if not x.startswith("--")]
src = args[0]; out = "pairs.json"
def flat(x):
    if isinstance(x, dict): return [x] if ("d" in x or "r" in x) else [y for v in x.values() for y in flat(v)]
    if isinstance(x, list): return [y for v in x for y in flat(v)]
    return []
txt = open(src).read(); dec = json.JSONDecoder(); i = 0; rows = []
while i < len(txt):
    while i < len(txt) and txt[i].isspace(): i += 1
    if i >= len(txt): break
    obj, i = dec.raw_decode(txt, i); rows += flat(obj)
if not rows:
    print("No rows found in", src, "->", txt[:300]); sys.exit(1)
mt = datetime.date.fromtimestamp(os.path.getmtime(src))
anchor = mt - datetime.timedelta(days=mt.weekday())          # Monday of the week the file was made
known = set(l.split(" ")[0] for l in open("codes.txt").read().split("\n")) if os.path.exists("codes.txt") else None
res = {"_w": str(anchor), "_war": {}}; unknown = {}
def put(a, b, tuples, war=None):
    a2, b2 = ALIAS.get(a, a), ALIAS.get(b, b)
    if a2 == b2: return
    flip = a2 > b2
    if flip: a2, b2 = b2, a2
    if known is not None and (a2 not in known or b2 not in known):
        for c in (a2, b2):
            if c not in known: unknown[c] = unknown.get(c, 0) + 1
        return
    key = a2 + "-" + b2
    t = [[p, r, (1 - i) if flip else i, n, tone, conf] for p, r, i, n, tone, conf in tuples]
    res.setdefault(key, []).extend(t)
    if war and any(war): res["_war"][key] = war
if "--weekly" in sys.argv:
    a, b = args[1], args[2]; tup = []
    for r in rows:
        if r.get("r") in (None, ""): continue
        d = datetime.date.fromisoformat(r["w"]); k = (anchor - d).days // 7 - 1
        if k < 0 or k > 50: continue
        p = 0 if k < 4 else 1 if k < 8 else 2 if k < 13 else 3
        tup.append([p, int(r["r"]), 0 if r["i"] == min(a, b) else 1, int(r["n"]), round(float(r["tone"])), int(r["conf"])])
    # merge weekly rows into period rows
    m = {}
    for p, rc, i, n, tone, conf in tup:
        v = m.setdefault((p, rc, i), [0, 0, 0]); v[0] += n; v[1] += tone; v[2] += conf
    put(min(a, b), max(a, b), [[p, rc, i, v[0], v[1], v[2]] for (p, rc, i), v in sorted(m.items())])
else:
    for row in rows:
        tup = []
        for s in row["d"].split(";"):
            p, r, i, n, tone, conf = s.split(",")
            tup.append([int(p), int(r), int(i), int(n), int(tone), int(conf)])
        put(row["a"], row["b"], tup, [int(row["w0"]), int(row["w1"]), int(row.get("l0", 0)), int(row.get("l1", 0))] if "w0" in row else None)
json.dump(res, open(out, "w"), separators=(",", ":"))
print(len(res) - 2, "pairs,", len(res["_war"]), "with government-on-government fighting ->", out, "(" + str(round(os.path.getsize(out) / 1e6, 2)) + " MB)")
if unknown: print("Codes not on the map (skipped):", sorted(unknown.items(), key=lambda x: -x[1])[:25])
