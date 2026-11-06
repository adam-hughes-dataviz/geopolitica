"""Real river lines (OpenStreetMap, via Overpass) for the hand-sourced rivers in geo_overrides.json that have no line.
Writes river_lines.json and adds the line to geography.json."""
import json, csv, io, time, urllib.request, urllib.parse, re
from shapely.geometry import LineString, Point, shape
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
ALT = {"Mekong": ["Mekong","Mékong","Tonlé Thom"], "Constitution River": ["Constitution River"], "Barka": ["Barka", "Gash", "Mereb-Gash"], "Võhandu": ["Võhandu", "Võhandu jõgi", "Vohandu"], "Térraba": ["Térraba", "Río Térraba", "Río Grande de Térraba", "Terraba"], "Severn": ["Severn", "River Severn", "Afon Hafren"], "Gudenå": ["Gudenå", "Gudenåen", "Gudenaa"], "Manas": ["Manas", "Manas River", "Drangme Chhu", "Drangmechhu", "Manas Chhu"], "Loa": ["Loa", "Río Loa", "Rio Loa"], "Belait": ["Belait", "Sungai Belait"], "Pärnu": ["Pärnu", "Pärnu jõgi", "Parnu"], "Fish River": ["Fish River", "Fischfluss", "Fish"], "Taedong": ["Taedong", "Taedong River", "Daedong"],
       "Váh": ["Váh", "Vah", "Waag"], "Vakhsh": ["Vakhsh", "Vaxsh", "Вахш"], "Mondego": ["Mondego", "Rio Mondego"], "Bosna": ["Bosna", "Rijeka Bosna"], "Chelif River": ["Chelif", "Cheliff", "Chélif", "Oued Chelif", "Oued Cheliff", "Oued Chéliff", "Chlef", "الشلف", "وادي الشلف"]}
for iso, v in over.items():
    r = v.get("river") if isinstance(v, dict) else None
    if not r or r.get("none") or r.get("line") or r.get("src") != "manual" or iso in out: continue
    i2 = cc.get(iso); names = ALT.get(r["n"], [r["n"]])
    rx = "^(" + "|".join(re.escape(n) for n in names) + ")$"
    q = '[out:json][timeout:90];area["ISO3166-1"="%s"]->.a;(relation["waterway"="river"]["name"~"%s",i](area.a);relation["waterway"="river"]["name:en"~"%s",i](area.a);way["waterway"="river"]["name"~"%s",i](area.a););out geom;' % (i2, rx, rx, rx)
    t = get("https://overpass-api.de/api/interpreter", urllib.parse.urlencode({"data": q}).encode()); time.sleep(3)
    try: els = json.loads(t)["elements"]
    except Exception: print(iso, r["n"], "overpass failed"); continue
    ways = []
    for e in els:
        if e.get("type") == "way" and e.get("geometry"): ways.append(LineString([(p["lon"], p["lat"]) for p in e["geometry"]]))
        for m in e.get("members", []):
            if m.get("type") == "way" and m.get("geometry") and m.get("role", "") in ("main_stream", "", "main"):
                ways.append(LineString([(p["lon"], p["lat"]) for p in m["geometry"]]))
    if not ways: print(iso, r["n"], "NO LINE FOUND", len(els)); continue
    g = linemerge(unary_union(ways))
    lines = sorted(list(g.geoms) if hasattr(g, "geoms") else [g], key=lambda l: -l.length)
    chain = list(lines[0].coords); rest = lines[1:]   # join pieces of one river that OpenStreetMap maps in separate parts
    joined = True
    while rest and joined:
        joined = False
        for l in sorted(rest, key=lambda l: -l.length):
            c = list(l.coords)
            best = min(((Point(chain[a]).distance(Point(c[b])), a, b) for a in (0, -1) for b in (0, -1)), key=lambda t: t[0])
            if best[0] < 0.2:
                if best[1] == 0: chain = chain[::-1]
                if best[2] == -1: c = c[::-1]
                chain = chain + c; rest.remove(l); joined = True; break
    print(iso, "pieces", len(lines), "joined", len(lines) - len(rest), [round(l.length * 111) for l in lines[:6]])
    main = LineString(chain).simplify(0.02)
    km = main.length * 111 * 0.8
    print(iso, r["n"], "line pts", len(main.coords), "approx km", round(km), "sourced", r["km"])
    out[iso] = {"line": rd(main.coords, 2), "others": [], "through": r.get("through", [])}
    geo.setdefault(iso, {}).setdefault("river", {}).update(out[iso])
json.dump(out, open("river_lines.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
json.dump(geo, open("geography.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("river lines:", sorted(out))
