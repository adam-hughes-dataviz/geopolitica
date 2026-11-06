"""Finds real lake outlines (OpenStreetMap, via Nominatim) for the hand-sourced lakes in geo_overrides.json.
Writes lake_outlines.json and adds the outline to geography.json. A shape is kept only if its name matches and its area
is within a factor of 3 of the sourced area (or, where no area is sourced, if it is a plausible lake size)."""
import json, math, time, csv, io, urllib.request, urllib.parse, unicodedata
from shapely.geometry import shape, LineString, Point
from shapely.ops import linemerge, polygonize, unary_union

UA = {"User-Agent": "geopolitica-dashboard/1.0 (https://github.com/adam-hughes-dataviz/geopolitica)"}
def get(u):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r: return r.read().decode("utf-8", "replace")
        except Exception: time.sleep(5 * (i + 1))
    return None
def norm(s): return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if c.isalnum())
def km2(g):
    lat = math.radians(g.centroid.y); return g.area * 111.32 ** 2 * math.cos(lat)
def rd(c, n): return [[round(x, n), round(y, n)] for x, y in c]

cc = {r["ISO3166-1-Alpha-3"]: r["ISO3166-1-Alpha-2"] for r in csv.DictReader(io.StringIO(get("https://raw.githubusercontent.com/datasets/country-codes/master/data/country-codes.csv")))}
over = json.load(open("geo_overrides.json", encoding="utf-8")); geo = json.load(open("geography.json", encoding="utf-8"))
try: out = json.load(open("lake_outlines.json", encoding="utf-8"))
except Exception: out = {}
ALT = {"Lake Engolasters": ["Estany d'Engolasters","Lake Engolasters","Engolasters"], "Lake Killarney": ["Lake Killarney"], "Band-e Haibat": ["Band-e Haibat","Band-i-Haibat","Haibat"], "Lake Kivu": ["Lake Kivu","Lac Kivu"], "Graeme Hall Swamp": ["Graeme Hall"], "Attersee": ["Attersee"], "Lac du Bourget": ["Lac du Bourget"], "Lake Sarysu": ["Sarysu", "Sarısu", "Sarısu gölü", "Lake Sarysu"], "Lake Ossa": ["Lac Ossa", "Lake Ossa", "Ossa"], "Lake Arenal": ["Lago Arenal", "Embalse Arenal", "Laguna de Arenal", "Lake Arenal"], "Lake Nasser": ["Lake Nasser", "Nasser Lake", "بحيرة ناصر"], "Lake Kossou": ["Lac de Kossou", "Kossou", "Lac Kossou"], "Zaza Reservoir": ["Presa Zaza", "Zaza", "Embalse Zaza"], "Buško Blato": ["Buško blato", "Busko Blato", "Buško jezero"], "Lac de la Plate Taille": ["Lac de la Plate Taille", "Plate Taille"], "Potworks Reservoir": ["Potworks", "Potworks Dam", "Potworks Reservoir"], "Dilolo Lake": ["Dilolo", "Lago Dilolo", "Lac Dilolo"], "Lake Tota": ["Lago de Tota", "Lago Tota", "Lake Tota"], "Vransko Lake": ["Vransko jezero", "Vransko Lake"], "Lake Bam": ["Lac de Bam", "Lac Bam", "Barrage de Bam"], "Lago Biaó": ["Lago Biao", "Lago de Moka", "Biao", "Moka"], "Kabji Hoka Tsho": ["Hokatsho", "Hoka Tsho", "Kabji Hoka Tsho"], "Lago Biaó": ["Lago Biao", "Lago de Moka", "Lake Moka"], "Tasek Merimbun": ["Merimbun", "Tasek Merimbun"],
       "Al Luzi Lake": ["Al Luzi", "Lake Al Luzi", "Luzi", "Lauzi", "Al Lawzi", "Al Luzi lake Bahrain"], "Laguna de Cuicocha": ["Cuicocha", "Laguna Cuicocha"], "Vuaqava lake": ["Vuaqava"], "Lake Rosa": ["Lake Rosa", "Lake Windsor"],
       "Černé jezero": ["Černé jezero"], "Lake Télé": ["Lake Tele", "Lac Tele", "Lac Télé"], "Akrotiri Salt Lake": ["Akrotiri Salt Lake", "Limassol Salt Lake", "Salt Lake", "Alyki"], "Chott Melrhir": ["Chott Melrhir", "Chott Melghir"],
       "Lake Nokoué": ["Lac Nokoué", "Lake Nokoue"], "Lake Burgas": ["Burgas Lake", "Burgasko ezero", "Burgaskoto ezero", "Vaya", "Вая", "Бургаско езеро"], "Blidinje Lake": ["Blidinje", "Blidinjsko jezero"], "Lake Ilopango": ["Lago de Ilopango", "Ilopango"]}
WD = {"Lake Sarysu": "Q2752255"}
PT = {"Lawzi Lake": (26.131886, 50.484901)}
def by_point(lat, lon):
    t = get("https://overpass-api.de/api/interpreter?" + urllib.parse.urlencode({"data": '[out:json][timeout:90];(way(around:200,%s,%s)["natural"="water"];relation(around:200,%s,%s)["natural"="water"];way(around:200,%s,%s)["water"];);out geom;' % ((lat, lon) * 3)}))
    try: els = json.loads(t)["elements"]
    except Exception: return None
    best = None
    for e in els:
        ls = []
        if e.get("type") == "way" and e.get("geometry"): ls.append(LineString([(p["lon"], p["lat"]) for p in e["geometry"]]))
        for m in e.get("members", []):
            if m.get("type") == "way" and m.get("geometry") and m.get("role") in ("outer", ""): ls.append(LineString([(p["lon"], p["lat"]) for p in m["geometry"]]))
        if not ls: continue
        pg = list(polygonize(unary_union(ls)))
        if not pg: continue
        g = unary_union(pg); d = g.distance(Point(lon, lat))
        if best is None or d < best[0] or (d == best[0] and g.area > best[1].area): best = (d, g)
    return best[1] if best else None
def by_wikidata(q):
    t = get("https://overpass-api.de/api/interpreter?" + urllib.parse.urlencode({"data": '[out:json][timeout:90];(relation["wikidata"="%s"];way["wikidata"="%s"];);out geom;' % (q, q)}))
    try: els = json.loads(t)["elements"]
    except Exception: return None
    ls = []
    for e in els:
        if e.get("type") == "way" and e.get("geometry"): ls.append(LineString([(p["lon"], p["lat"]) for p in e["geometry"]]))
        for m in e.get("members", []):
            if m.get("type") == "way" and m.get("geometry") and m.get("role") in ("outer", ""): ls.append(LineString([(p["lon"], p["lat"]) for p in m["geometry"]]))
    if not ls: return None
    pg = list(polygonize(unary_union(ls)))
    return unary_union(pg) if pg else None
for iso, v in over.items():
    lk = v.get("lake") if isinstance(v, dict) else None
    if not lk or lk.get("none") or lk.get("src") != "manual" or "line" in lk: continue
    if (geo.get(iso, {}).get("lake") or {}).get("poly") and iso not in out: continue
    i2 = (cc.get(iso) or "").lower(); got = None
    if lk["n"] in PT:
        g0 = by_point(*PT[lk["n"]])
        if g0 is not None and not g0.is_empty:
            got = (0, g0, km2(g0)); lk["km2"] = round(km2(g0), 2); geo[iso]["lake"]["km2"] = lk["km2"]; print(iso, lk["n"], "-> point outline", lk["km2"], "km2")
    if lk["n"] in WD and not got:
        g0 = by_wikidata(WD[lk["n"]])
        if g0 is not None and not g0.is_empty:
            got = (0, g0, km2(g0)); print(iso, lk["n"], "-> wikidata outline", round(km2(g0), 2), "km2")
    for name in ([] if got else ALT.get(lk["n"], [lk["n"]])):
        t = get("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": name, "countrycodes": i2, "format": "jsonv2", "polygon_geojson": 1, "limit": 10})); time.sleep(1.5)
        try: res = json.loads(t)
        except Exception: continue
        for r in res:
            gj = r.get("geojson") or {}
            if gj.get("type") not in ("Polygon", "MultiPolygon"): continue
            if not any(norm(a) in norm(r.get("display_name", "").split(",")[0]) or norm(r.get("display_name", "").split(",")[0]) in norm(a) for a in ALT.get(lk["n"], [lk["n"]])): continue
            g = shape(gj); a = km2(g)
            ok = (lk["km2"] / 3 <= a <= lk["km2"] * 3) if lk.get("km2") else 0.05 <= a <= 500
            print(iso, name, "->", r.get("display_name", "")[:60], round(a, 2), "km2", "OK" if ok else "rejected")
            if ok and (got is None or abs(math.log(a / (lk.get("km2") or a))) < got[0]): got = (abs(math.log(a / (lk.get("km2") or a))), g, a)
        if got: break
    if not got: print(iso, lk["n"], "NO OUTLINE FOUND"); continue
    g = got[1]; polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
    polys = sorted(polys, key=lambda p: -p.area)[:4]
    rings = [rd(p.simplify(0.0015 if p.area < 0.01 else 0.01).exterior.coords, 4) for p in polys]
    out[iso] = rings; geo.setdefault(iso, {}).setdefault("lake", {})["poly"] = rings
    if not lk.get("km2"): print(iso, "outline area (not shown on site):", round(got[2], 2))
json.dump(out, open("lake_outlines.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
json.dump(geo, open("geography.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("outlines:", sorted(out))
