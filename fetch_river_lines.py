"""Real river lines (OpenStreetMap, via Overpass) for the hand-sourced rivers in geo_overrides.json that have no line.
Writes river_lines.json and adds the line to geography.json."""
import json, csv, io, time, urllib.request, urllib.parse, re
from shapely.geometry import LineString, shape
from shapely.ops import linemerge, unary_union
UA = {"User-Agent": "geopolitica-dashboard/1.0 (https://github.com/adam-hughes-dataviz/geopolitica)"}
def get(u, data=None):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, data=data, headers=UA), timeout=120) as r: return r.read().decode("utf-8", "replace")
        except Exception: time.sleep(8 * (i + 1))
    return None
def rd(c, n): return [[round(x, n), round(y, n)] for x, y in c]
cc = {r["ISO3166-1-Alpha-3"]: r["ISO3166-1-Alpha-2"] for r in csv.DictReader(io.StringIO(get("https://raw.githubusercontent.com/datasets/country-codes/master/data/country-codes.csv")))}
over = json.load(open("geo_overrides.json", encoding="utf-8")); geo = json.load(open("geography.json", encoding="utf-8"))
try: out = json.load(open("river_lines.json", encoding="utf-8"))
except Exception: out = {}
ALT = {"Belait": ["Belait", "Sungai Belait"], "Pärnu": ["Pärnu", "Pärnu jõgi", "Parnu"], "Fish River": ["Fish River", "Fischfluss", "Fish"], "Taedong": ["Taedong", "Taedong River", "Daedong"],
       "Váh": ["Váh", "Vah", "Waag"], "Vakhsh": ["Vakhsh", "Vaxsh", "Вахш"], "Mondego": ["Mondego", "Rio Mondego"], "Bosna": ["Bosna", "Rijeka Bosna"]}
for iso, v in over.items():
    r = v.get("river") if isinstance(v, dict) else None
    if not r or r.get("none") or r.get("line") or r.get("src") != "manual" or iso in out: continue
    i2 = cc.get(iso); names = ALT.get(r["n"], [r["n"]])
    rx = "^(" + "|".join(re.escape(n) for n in names) + ")$"
    q = '[out:json][timeout:90];area["ISO3166-1"="%s"]->.a;(relation["waterway"="river"]["name"~"%s",i](area.a);relation["waterway"="river"]["name:en"~"%s",i](area.a););out geom;' % (i2, rx, rx)
    t = get("https://overpass-api.de/api/interpreter", urllib.parse.urlencode({"data": q}).encode()); time.sleep(3)
    try: els = json.loads(t)["elements"]
    except Exception: print(iso, r["n"], "overpass failed"); continue
    ways = []
    for e in els:
        for m in e.get("members", []):
            if m.get("type") == "way" and m.get("geometry") and m.get("role", "") in ("main_stream", "", "main"):
                ways.append(LineString([(p["lon"], p["lat"]) for p in m["geometry"]]))
    if not ways: print(iso, r["n"], "NO LINE FOUND", len(els)); continue
    g = linemerge(unary_union(ways))
    lines = sorted(list(g.geoms) if hasattr(g, "geoms") else [g], key=lambda l: -l.length)
    main = lines[0].simplify(0.02)
    km = main.length * 111 * 0.8
    print(iso, r["n"], "line pts", len(main.coords), "approx km", round(km), "sourced", r["km"])
    out[iso] = {"line": rd(main.coords, 2), "others": [], "through": r.get("through", [])}
    geo.setdefault(iso, {}).setdefault("river", {}).update(out[iso])
json.dump(out, open("river_lines.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
json.dump(geo, open("geography.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("river lines:", sorted(out))
