"""Build geography.json: area, highest and lowest points, biggest river and biggest lake per country.
Sources (all free, public): CIA World Factbook (github.com/factbook/factbook.json) for area and elevation,
Natural Earth (github.com/nvkelso/natural-earth-vector) for river and lake shapes, lengths and areas.
Run monthly on GitHub Actions. Nothing here is typed by hand except the short geo_overrides.json list."""
import csv, difflib, glob, html, json, math, os, re, sys, time, unicodedata, urllib.request, urllib.parse
import numpy as np
from shapely.geometry import shape, mapping, MultiLineString, LineString, Point, box
from shapely.ops import linemerge, unary_union, transform
from shapely.strtree import STRtree

FB_DIR = os.environ.get("FB_DIR", "factbook.json")
CACHE = os.environ.get("NE_DIR", "ne_cache")
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
CODES = "https://raw.githubusercontent.com/datasets/country-codes/master/data/country-codes.csv"
R_EARTH = 6371.0088
LAKE_ALIAS = {"scutari": "skadar"}   # older spelling used by the Factbook

def get(url, path):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "geopolitica-geography/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
                f.write(r.read())
            return path
        except Exception as e:
            print("retry", url, e); time.sleep(3 * (i + 1))
    raise SystemExit("could not download " + url)

def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[1], a[0], b[1], b[0]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(h))

def length_km(g):
    if g.is_empty: return 0.0
    parts = g.geoms if hasattr(g, "geoms") else [g]
    t = 0.0
    for p in parts:
        if p.geom_type != "LineString": continue
        c = list(p.coords)
        t += sum(hav(c[i], c[i + 1]) for i in range(len(c) - 1))
    return t

def laea(lon0, lat0):
    p0, l0 = math.radians(lat0), math.radians(lon0)
    def f(x, y, z=None):
        x = np.radians(np.asarray(x, float)); y = np.radians(np.asarray(y, float))
        k = np.sqrt(2 / (1 + math.sin(p0) * np.sin(y) + math.cos(p0) * np.cos(y) * np.cos(x - l0)))
        return (R_EARTH * k * np.cos(y) * np.sin(x - l0), R_EARTH * k * (math.cos(p0) * np.sin(y) - math.sin(p0) * np.cos(y) * np.cos(x - l0)))
    return f

def area_km2(poly):
    c = poly.representative_point()
    return transform(laea(c.x, c.y), poly).area

def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "").replace("&nbsp;", " ").replace(" ", " ")).strip()

def num(s):
    return float(s.replace(",", ""))

# ---------- Factbook ----------
def load_factbook():
    codes = get(CODES, os.path.join(CACHE, "country-codes.csv"))
    fips = {}
    for r in csv.DictReader(open(codes, encoding="utf-8")):
        if r["ISO3166-1-Alpha-3"] and r["FIPS"]:
            fips[r["FIPS"].lower()] = r["ISO3166-1-Alpha-3"]
    out = {}
    for f in glob.glob(os.path.join(FB_DIR, "*", "*.json")):
        c = os.path.basename(f)[:-5]
        if c in fips:
            try: out[fips[c]] = json.load(open(f, encoding="utf-8")).get("Geography") or {}
            except Exception: pass
    return out

def parse_area(g):
    a = clean(((g.get("Area") or {}).get("total ") or (g.get("Area") or {}).get("total") or {}).get("text"))
    if not a: return None
    met = re.search(r"([\d,]+)\s*sq km\s*\(metropolitan", a)
    if met: return int(num(met.group(1)))
    mm = re.search(r"([\d.]+)\s*million\s*sq km", a)
    if mm: return int(round(float(mm.group(1)) * 1e6, -3))
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*sq km", a)
    return int(round(num(m.group(1)))) if m else None

def parse_point(t):
    t = clean(t)
    if not t: return None
    m = list(re.finditer(r"(-?[\d,]+(?:\.\d+)?)\s*m\b", t)) or list(re.finditer(r"(-?[\d,]{2,})\s*$", t))
    if not m: return None
    last = m[-1]
    v = num(last.group(1))
    name = re.sub(r"\([^)]*\)", "", t[:last.start()])
    name = re.sub(r"[;,:\-\s]+$", "", name).strip()
    if re.search(r"unnamed|not named|^$", name, re.I): name = "Unnamed point"
    return {"n": name, "m": int(round(v))}

def norm(s):
    s = unicodedata.normalize("NFKD", html.unescape(s or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(lake|lago|lac|lough|loch|river|rio|riu|fleuve|sea|reservoir|embalse|laguna|lagoa)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", "", s)

def names_of(raw):
    """Plausible spellings of a Factbook name: the bare name plus any short English alternative in brackets."""
    raw = re.sub(r"\[[^\]]*\]", " ", raw.replace("*", ""))
    alts = [a for a in re.findall(r"\(([^)]*)\)", raw) if not re.search(r"shared|endorheic|basin|reservoir|salt|fresh|and ", a, re.I) and len(a) < 30]
    base = re.split(r"\(|,|\b[Rr]iver (?:source|mouth)\b|\bsource\b|\bmouth\b", raw)[0]
    base = re.sub(r"\b[Rr]iver\s*$", "", base)
    out = []
    for x in [base] + alts:
        for y in x.split("/"):
            y = re.sub(r"^(Rio|R\u00edo|River)\s+", "", re.sub(r"\s+", " ", y).strip())
            if y and y not in out: out.append(y)
    return out

def parse_rivers(g):
    t = clean((g.get("Major rivers (by length in km)") or {}).get("text"))
    t = re.sub(r"note:.*$", "", t)
    out = []
    for part in t.split(";"):
        m = re.search(r"^(.*?)\s+[-\u2013]\s+([\d,]+)\s*km", part.strip())
        if not m: continue
        raw = m.group(1)
        shared = bool(re.search(r"shared", raw, re.I))
        out.append({"names": names_of(raw), "km": int(num(m.group(2))), "shared": shared})
    return out

def parse_lakes(g):
    out = []
    for k, v in (g.get("Major lakes (area sq km)") or {}).items():
        t = clean((v or {}).get("text") if isinstance(v, dict) else "")
        for part in re.split(r";", t):
            m = re.search(r"^(.*?)\s+[-\u2013]\s+([\d,]+)", part.strip())
            if not m: continue
            raw = m.group(1)
            out.append({"names": names_of(raw), "km2": int(num(m.group(2))), "shared": bool(re.search(r"shared", raw, re.I))})
    return out

# ---------- Natural Earth ----------
def load_ne():
    adm = json.load(open(get(NE + "ne_50m_admin_0_countries.geojson", os.path.join(CACHE, "adm.geojson")), encoding="utf-8"))
    land = json.load(open(get(NE + "ne_50m_land.geojson", os.path.join(CACHE, "land.geojson")), encoding="utf-8"))
    lakes = json.load(open(get(NE + "ne_10m_lakes.geojson", os.path.join(CACHE, "lakes.geojson")), encoding="utf-8"))
    # lagoons and inland seas that Natural Earth keeps in its marine layer (Caspian Sea, Lake Maracaibo, Patos and Szczecin lagoons)
    marine = json.load(open(get(NE + "ne_10m_geography_marine_polys.geojson", os.path.join(CACHE, "marine.geojson")), encoding="utf-8"))
    lakes["features"] += [f for f in marine["features"] if f["properties"].get("featurecla") == "lagoon" or f["properties"].get("name") == "Caspian Sea"]
    rivers = json.load(open(get(NE + "ne_10m_rivers_lake_centerlines.geojson", os.path.join(CACHE, "rivers.geojson")), encoding="utf-8"))
    return adm, land, lakes, rivers

def rd(coords, n):
    return [[round(x, n), round(y, n)] for x, y in coords]

def cluster(gs):
    """Group same-name river segments into connected systems, so two rivers sharing a name stay separate."""
    groups = []
    for g in gs:
        hit = [k for k, grp in enumerate(groups) if any(g.distance(h) < 0.35 for h in grp)]
        merged = [g]
        for k in sorted(hit, reverse=True):
            merged += groups.pop(k)
        groups.append(merged)
    return groups

LAKES_PKG = "https://registry.npmjs.org/@geo-maps/earth-lakes-1km/-/earth-lakes-1km-0.6.0.tgz"   # OpenStreetMap lakes, 1 km, no names

def load_osm_lakes():
    """Unnamed OpenStreetMap lake outlines (ODbL), downloaded from the npm registry."""
    import tarfile
    p = get(LAKES_PKG, os.path.join(CACHE, "osm_lakes.tgz"))
    with tarfile.open(p) as t:
        d = json.load(t.extractfile("package/map.geo.json"))
    polys = [shape({"type": "Polygon", "coordinates": c}) for c in d["geometries"][0]["coordinates"]]
    return polys, STRtree(polys)

def area_any(g):
    return sum(area_km2(x) for x in (g.geoms if hasattr(g, "geoms") else [g]) if x.geom_type == "Polygon")

def outline_at(pt, km2, osm, land_u):
    """Outline of a lake Natural Earth lacks, found from its known location (lake_points.json) and the Factbook area.
    1) OpenStreetMap lakes near the point, merged into one cluster whose area is closest to the Factbook figure;
    2) for a coastal lagoon, the sea inside the Natural Earth coast near the point, with the narrow mouth cut off."""
    polys, tree = osm
    near = [polys[i] for i in tree.query(pt.buffer(0.6)) if polys[i].distance(pt) < 0.6]
    cl = []
    for p in near:
        m = [p]
        for c in [c for c in cl if c[0].distance(p) < 0.06]:
            m += c[1]; cl.remove(c)
        cl.append((unary_union(m), m))
    best = None
    for g, parts in cl:
        a = area_any(g); r = a / km2
        big = max(area_km2(x) for x in parts)
        if 0.15 <= r <= 2.5 and big >= 0.4 * a:   # reject scattered fragments
            sc = g.distance(pt) + abs(math.log(r)) * 0.15
            if best is None or sc < best[0]: best = (sc, g)
    if best:
        g = best[1]
        keep = [x for x in (g.geoms if hasattr(g, "geoms") else [g]) if x.geom_type == "Polygon" and area_km2(x) >= 0.03 * area_any(g)]
        return unary_union(keep), "OpenStreetMap lakes"
    lo, la = pt.x, pt.y
    water = box(lo - 1.5, la - 1.5, lo + 1.5, la + 1.5).difference(land_u)
    comps = [x for x in (water.geoms if hasattr(water, "geoms") else [water]) if x.distance(pt) < 0.05]
    if comps:
        c = max(comps, key=lambda x: x.area); bestl = None
        for r in (0.01, 0.02, 0.03, 0.04, 0.06, 0.08, 0.1, 0.15, 0.2, 0.3):
            o = c.buffer(-r).buffer(r)
            cs = [x for x in (o.geoms if hasattr(o, "geoms") else [o]) if x.distance(pt) < 0.05]
            if not cs: break
            m = max(cs, key=lambda x: x.area); q = area_any(m) / km2
            if 0.6 <= q <= 1.6 and (bestl is None or abs(math.log(q)) < bestl[0]): bestl = (abs(math.log(q)), m)
        if bestl: return bestl[1], "coast outline"
    return None, ""

# ---- Wikidata and OpenStreetMap fill: names, lengths and shapes for countries the sources above leave empty
WD_UA = {"User-Agent": "geopolitica-dashboard/1.0 (https://github.com/adam-hughes-dataviz/geopolitica)"}
def wd_http(url, accept="application/json"):
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers=dict(WD_UA, Accept=accept))
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (400, 404): return None
            time.sleep(15 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    return None

def wd_sparql(q):
    t = wd_http("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q))
    time.sleep(3)
    try: return json.loads(t)["results"]["bindings"]
    except Exception: return None

def wd_rows(rows):
    """One record per Wikidata item: name, longest length or biggest area, OSM relation, countries it lies in."""
    out = {}
    for r in rows or []:
        q = r["r"]["value"].rsplit("/", 1)[-1]
        d = out.setdefault(q, {"q": q, "n": r["rl"]["value"], "v": 0.0, "osm": None, "cc": set(), "i2": None})
        try: d["v"] = max(d["v"], float(r["v"]["value"])) if "v" in r else d["v"]
        except Exception: pass
        if "osm" in r: d["osm"] = r["osm"]["value"]
        d["cc"] |= set(x for x in r["ccs"]["value"].split(",") if x)
        if "i2" in r: d["i2"] = r["i2"]["value"]
    return list(out.values())

def osm_parts(rel):
    t = wd_http("https://api.openstreetmap.org/api/0.6/relation/%s/full.json" % rel); time.sleep(1)
    try: els = json.loads(t)["elements"]
    except Exception: return []
    nodes = {e["id"]: (e["lon"], e["lat"]) for e in els if e["type"] == "node"}
    ways = []
    for e in els:
        if e["type"] == "way":
            pts = [nodes[n] for n in e["nodes"] if n in nodes]
            if len(pts) >= 2: ways.append(LineString(pts))
    return ways

def nominatim_geom(name, q, i2, kinds):
    """Shape of a named feature from OpenStreetMap's search, trusting only a result tagged with the same Wikidata item."""
    u = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": name, "countrycodes": (i2 or "").lower(), "format": "jsonv2", "extratags": 1, "polygon_geojson": 1, "limit": 10})
    t = wd_http(u); time.sleep(1.5)
    try: res = json.loads(t)
    except Exception: return None
    for r in res:
        if (r.get("extratags") or {}).get("wikidata") == q and r.get("geojson", {}).get("type") in kinds:
            return shape(r["geojson"])
    return None

def wd_river(iso, C, coast):
    q = '''SELECT ?r ?rl ?v ?osm ?i2 (GROUP_CONCAT(DISTINCT ?cc;separator=",") AS ?ccs) WHERE {
      ?cx wdt:P298 "%s"; wdt:P297 ?i2. VALUES ?t { wd:Q4022 wd:Q355304 wd:Q47521 } ?r wdt:P31 ?t; wdt:P17 ?cx; wdt:P17 ?c2. ?c2 wdt:P298 ?cc.
      OPTIONAL{?r wdt:P2043 ?v} OPTIONAL{?r wdt:P402 ?osm} ?r rdfs:label ?rl FILTER(LANG(?rl)="en")
    } GROUP BY ?r ?rl ?v ?osm ?i2''' % iso
    recs = [d for d in wd_rows(wd_sparql(q)) if d["v"] > 0]
    inside = sorted([d for d in recs if d["cc"] == {iso}], key=lambda d: -d["v"])
    thr = sorted([d for d in recs if iso in d["cc"] and len(d["cc"]) > 1], key=lambda d: -d["v"])
    best = inside[0] if inside else (thr[0] if thr else None)
    if not best: return None
    orv = {"n": best["n"], "km": int(round(best["v"])), "src": "wd"}
    if best["cc"] != {iso}: orv["through"] = sorted(best["cc"] - {iso})
    g = None
    if best["osm"]:
        parts = osm_parts(best["osm"])
        if parts: g = linemerge(parts)
    if g is None: g = nominatim_geom(best["n"], best["q"], best["i2"], ("LineString", "MultiLineString"))
    if g is not None and iso in C:
        if orv.get("through"): g = g.intersection(C[iso].buffer(0.05))
        if not g.is_empty:
            m = linemerge(g) if g.geom_type == "MultiLineString" else g
            lines = sorted(list(m.geoms) if hasattr(m, "geoms") else [m], key=lambda l: -l.length)
            main = lines[0].simplify(0.02)
            orv["line"] = rd(main.coords, 2); orv["others"] = []
            ends = [Point(main.coords[0]), Point(main.coords[-1])]
            d = [coast.distance(e) * 111 for e in ends]
            if min(d) < 40 and max(d) > 120: orv["mouth"] = 0 if d[0] < d[1] else 1
    return orv

def wd_lake(iso, C):
    q = '''SELECT ?r ?rl ?v ?osm ?i2 (GROUP_CONCAT(DISTINCT ?cc;separator=",") AS ?ccs) WHERE {
      ?cx wdt:P298 "%s"; wdt:P297 ?i2. ?r wdt:P31/wdt:P279* wd:Q23397; wdt:P17 ?cx; wdt:P17 ?c2. ?c2 wdt:P298 ?cc.
      OPTIONAL{?r wdt:P2046 ?v} OPTIONAL{?r wdt:P402 ?osm} ?r rdfs:label ?rl FILTER(LANG(?rl)="en")
    } GROUP BY ?r ?rl ?v ?osm ?i2''' % iso
    recs = wd_rows(wd_sparql(q))
    if not recs: return None
    recs.sort(key=lambda d: (-d["v"], 0 if d["osm"] else 1))
    for best in recs[:4]:   # biggest first; a lake with no shape or area is skipped for the next
        g = None
        if best["osm"]:
            parts = osm_parts(best["osm"])
            if parts:
                from shapely.ops import polygonize
                polys = list(polygonize(unary_union(parts)))
                if polys: g = unary_union(polys)
        if g is None: g = nominatim_geom(best["n"], best["q"], best["i2"], ("Polygon", "MultiPolygon"))
        km2, approx = best["v"], False
        if g is not None and g.geom_type in ("Polygon", "MultiPolygon"):
            polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
            if km2 <= 0: km2, approx = sum(area_km2(p) for p in polys), True
        if km2 <= 0: continue
        lk = {"n": best["n"], "km2": int(round(km2)) if km2 >= 1 else round(km2, 2), "shared": sorted(best["cc"] - {iso}), "src": "wd"}
        if approx: lk["approx"] = 1
        if g is not None and g.geom_type in ("Polygon", "MultiPolygon"):
            polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
            lk["poly"] = [rd(p.simplify(0.01).exterior.coords, 3) for p in sorted(polys, key=lambda p: -p.area)[:4]]
        return lk
    return None

def wikidata_fill(out, C, coast, targets):
    missing = []
    for iso in targets:
        o = out.setdefault(iso, {})
        if not o.get("river"):
            r = wd_river(iso, C, coast)
            if r: o["river"] = r; print("wikidata river", iso, r["n"], r["km"], "line" if r.get("line") else "NO LINE")
            else: missing.append(("river", iso))
        if not o.get("lake"):
            l = wd_lake(iso, C)
            if l: o["lake"] = l; print("wikidata lake", iso, l["n"], l["km2"], "outline" if l.get("poly") else "NO OUTLINE")
            else: missing.append(("lake", iso))
        if not o: out.pop(iso, None)
    print("STILL MISSING (need a source from you):", missing)

def main():
    fb = load_factbook()
    adm, land, lakes, rivers = load_ne()
    over = json.load(open("geo_overrides.json", encoding="utf-8")) if os.path.exists("geo_overrides.json") else {}
    by = {}
    for f in adm["features"]:
        p = f["properties"]
        iso = p.get("ISO_A3_EH") if p.get("ISO_A3_EH") not in (None, "-99") else p.get("ADM0_A3")
        by.setdefault(iso, []).append(shape(f["geometry"]))
    C = {k: unary_union(v) for k, v in by.items()}
    isos = list(C); trees = STRtree([C[k] for k in isos])
    LAND_U = unary_union([shape(f["geometry"]) for f in land["features"]]); coast = LAND_U.boundary
    LAKE_PTS = json.load(open("lake_points.json", encoding="utf-8")) if os.path.exists("lake_points.json") else {}
    OSM = [None]
    # ---- lakes (Natural Earth shapes; same-name pieces merged, area from the merged outline)
    pieces = {}; alts = {}
    for f in lakes["features"]:
        p = f["properties"]; n = p.get("name_en") or p.get("name")
        if not n: continue
        g = shape(f["geometry"])
        if not g.is_empty:
            pieces.setdefault(n, []).append(g)
            if p.get("name") and p.get("name") != n: alts.setdefault(n, set()).add(p["name"])   # e.g. English 'Nyanza' vs local 'Lake Victoria'
    L = []
    for n, gs in pieces.items():
        g = unary_union(gs)
        sh = {}
        for i in trees.query(g):
            inter = g.intersection(C[isos[i]])
            if not inter.is_empty and inter.area / g.area >= 0.05: sh[isos[i]] = inter.area / g.area
        L.append({"n": n, "a": area_km2(g) if g.geom_type == "Polygon" else sum(area_km2(x) for x in g.geoms), "g": g, "sh": sh, "k": norm(n), "alt": alts.get(n, set())})
    ltree = STRtree([l["g"] for l in L])
    Lk = {}
    for l in L: Lk.setdefault(l["k"], []).append(l)
    for l in L:
        for al in l["alt"]:
            if norm(al) != l["k"]: Lk.setdefault(norm(al), []).append(l)
    # ---- rivers (Natural Earth shapes; systems clustered by name and contact)
    RV = {}
    for f in rivers["features"]:
        p = f["properties"]
        if p.get("featurecla") != "River": continue
        n = p.get("name_en") or p.get("name")
        if n: RV.setdefault(n, []).append(shape(f["geometry"]))
    RIV = []
    for n, gs in RV.items():
        for grp in cluster(gs):
            full = unary_union(grp)
            RIV.append({"n": n, "g": full, "km": length_km(full), "k": norm(n)})
    rtree = STRtree([r["g"] for r in RIV])
    Rk = {}
    for r in RIV: Rk.setdefault(r["k"], []).append(r)
    out = {}
    for iso in C:
        o = {}
        f = fb.get(iso) or {}
        cg = C[iso].buffer(0.03)
        if f:
            ar = parse_area(f)
            if ar: o["area"] = {"km2": ar}
            e = f.get("Elevation") or {}
            hi = parse_point((e.get("highest point") or {}).get("text")); lo = parse_point((e.get("lowest point") or {}).get("text"))
            if hi: o["hi"] = hi
            if lo: o["lo"] = lo
        for k, v in (over.get(iso) or {}).items():
            if k in ("hi", "lo"): o[k] = v
            elif k == "area": o["area"] = {"km2": v}
        # ---- biggest lake: Factbook list first (largest), shape matched by name; else largest lake on the map
        lake = None
        fl = sorted(parse_lakes(f), key=lambda x: -x["km2"])
        if fl:
            b = fl[0]; shp = None
            near = [L[i] for i in ltree.query(cg)]
            for nm in b["names"]:
                for cand in Lk.get(norm(nm), []):
                    if (cand["sh"].get(iso, 0) >= 0.05 or cand in near) and (shp is None or cand["a"] > shp["a"]): shp = cand
            if shp is None:   # spelling differs (e.g. Quinghai / Qinghai): closest name among lakes touching this country
                best = 0
                for cand in near:
                    for nm in b["names"]:
                        k1 = LAKE_ALIAS.get(norm(nm), norm(nm)); k2 = cand["k"]
                        rr = difflib.SequenceMatcher(None, k1, k2).ratio()
                        if min(len(k1), len(k2)) >= 3 and (k1 in k2 or k2 in k1): rr = max(rr, 0.9)   # Toba / Danau Toba, Uvs / Uvs Nuur
                        if rr > best and rr >= 0.8: best, shp = rr, cand
            if shp is None and iso in LAKE_PTS:   # not in Natural Earth: outline from the lake's known location
                if OSM[0] is None: OSM[0] = load_osm_lakes()
                g, how = outline_at(Point(*LAKE_PTS[iso]), b["km2"], OSM[0], LAND_U)
                if g is not None and not g.is_empty: shp = {"g": g, "sh": {}, "n": "", "a": area_any(g)}
                print("lake outline", iso, b["names"][0], ("found: " + how) if shp else "NOT FOUND")
            lake = {"n": b["names"][0], "km2": b["km2"], "shared": [], "shp": shp}
            if shp:
                sh = dict(shp["sh"])
                if sum(sh.values()) < 0.3:   # inland sea or lagoon: sharing by coastline contact instead of land overlap
                    sh = {isos[i]: 1 for i in trees.query(shp["g"].buffer(0.03)) if C[isos[i]].distance(shp["g"]) < 0.03}
                lake["shared"] = sorted(c for c in sh if c != iso and sh[c] >= 0.1)
        else:
            cand = [l for l in L if l["sh"].get(iso, 0) >= 0.05]
            if cand:
                b = max(cand, key=lambda l: l["a"])
                lake = {"n": b["n"], "km2": int(round(b["a"])), "shared": sorted(c for c in b["sh"] if c != iso and b["sh"][c] >= 0.1), "shp": b, "approx": True}
        if lake is None:   # a lake touching the coast or border, then the biggest OpenStreetMap lake inside the country (unnamed)
            near = [L[i] for i in ltree.query(cg) if L[i]["g"].distance(C[iso]) < 0.05]
            if near:
                b = max(near, key=lambda l: l["a"])
                lake = {"n": b["n"], "km2": int(round(b["a"])), "shared": sorted(c for c in b["sh"] if c != iso and b["sh"][c] >= 0.1), "shp": b, "approx": True}
        if lake is None:
            if OSM[0] is None: OSM[0] = load_osm_lakes()
            polys_o, tree_o = OSM[0]; best_o = None
            for i in tree_o.query(C[iso]):
                p = polys_o[i]
                if C[iso].contains(p.representative_point()):
                    a_ = area_km2(p)
                    if a_ >= 2 and (best_o is None or a_ > best_o[0]): best_o = (a_, p)
            if best_o: lake = {"n": "Unnamed lake", "km2": int(round(best_o[0])), "shared": [], "shp": {"g": best_o[1], "sh": {}}, "approx": True}
        if lake:
            ol = {"n": lake["n"], "km2": lake["km2"], "shared": lake["shared"]}
            if lake.get("approx"): ol["approx"] = 1
            if lake["shp"]:
                g = lake["shp"]["g"].simplify(0.01)
                polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
                ol["poly"] = [rd(p.exterior.coords, 3) for p in sorted(polys, key=lambda p: -p.area)[:4]]
            o["lake"] = ol
        # ---- biggest river: the longest one that stays entirely inside the country
        allin = []
        for i in rtree.query(cg):
            r = RIV[i]; ins = r["g"].intersection(cg); li = length_km(ins)
            if li >= 25: allin.append((li, r, ins))
        allin.sort(key=lambda t: -t[0])
        # Longest river that stays entirely inside this country. The Factbook's "shared" flag is trusted, and a river it does
        # not flag is still dropped when the map shows it leaving the country. Rivers the Factbook does not list use the map length.
        cg2 = C[iso].buffer(0.1)
        def stays_in(r):
            if length_km(r["g"].intersection(cg2)) / max(r["km"], 1e-6) < 0.95: return False
            for j in trees.query(r["g"]):   # a river that runs along or across a border is shared, even when the Factbook does not say so
                c = isos[j]
                if c != iso and length_km(r["g"].intersection(C[c].buffer(0.03))) >= 25: return False
            eb = r["g"].boundary   # a river that carries on across the border under another name (Tajo / Tejo) is not contained
            for pt in (list(eb.geoms) if hasattr(eb, "geoms") else [eb]):
                for j in rtree.query(pt.buffer(0.05)):
                    r2 = RIV[j]
                    if r2 is r or r2["g"].boundary.distance(pt) >= 0.05: continue   # end-to-end contact only; joining a bigger river sideways is fine
                    if r2["km"] - length_km(r2["g"].intersection(cg2)) >= 15: return False
            return True
        cands = []; used = set(); shp = None
        for x in parse_rivers(f):
            m = None
            for nm in x["names"]:
                for li, r, ins in allin:
                    if r["k"] == norm(nm) and (m is None or li > m[0]): m = (li, r, ins)
            if m is not None: used.add(id(m[1]))
            if (m is None and x["shared"]) or (m is not None and not stays_in(m[1])): continue   # the Factbook flag can be wrong (it calls the Vistula shared), so the map decides when it has the shape
            cands.append({"km": x["km"], "n": x["names"][1] if len(x["names"]) > 1 else x["names"][0], "approx": False, "shp": m})
        for li, r, ins in allin:
            if id(r) not in used and not re.search(r"branch|canal|distributary", r["n"], re.I) and stays_in(r):
                cands.append({"km": int(round(r["km"], -1)), "n": r["n"], "approx": True, "shp": (li, r, ins)})
        if os.environ.get("DBG") and iso in os.environ["DBG"].split(","): print(iso, [(c["n"], c["km"], c["approx"]) for c in cands], "| FB:", [(x["names"][0], x["km"], x["shared"]) for x in parse_rivers(f)][:8])
        best = max(cands, key=lambda c: c["km"]) if cands else None
        if not best:   # none stays inside: the longest river that flows through it (listed as shared on the page)
            fr_ = parse_rivers(f)
            if fr_:
                pk = max(fr_, key=lambda x: x["km"]); m = None
                for nm in pk["names"]:
                    for li, r, ins in allin:
                        if r["k"] == norm(nm) and (m is None or li > m[0]): m = (li, r, ins)
                best = {"km": pk["km"], "n": pk["names"][1] if len(pk["names"]) > 1 else pk["names"][0], "approx": False, "shp": m}
            elif allin:
                li, r, ins = allin[0]
                best = {"km": int(round(r["km"], -1)), "n": r["n"], "approx": True, "shp": (li, r, ins)}
        if best:
            name, km, approx, shp = best["n"], best["km"], best["approx"], best["shp"]
            orv = {"n": name, "km": km}
            if approx: orv["approx"] = 1
            if shp:
                li, r, inside = shp
                m = linemerge(inside) if inside.geom_type == "MultiLineString" else inside
                lines = sorted(list(m.geoms) if hasattr(m, "geoms") else [m], key=lambda l: -l.length)
                main = lines[0].simplify(0.02)
                orv["line"] = rd(main.coords, 2)
                orv["others"] = []
                for lj, rj, ins in allin[:7]:
                    if rj is r: continue
                    s = ins.simplify(0.04); parts = list(s.geoms) if hasattr(s, "geoms") else [s]
                    orv["others"].append([rd(p.coords, 2) for p in parts if p.geom_type == "LineString"])
                    if len(orv["others"]) >= 5: break
                thr = []
                for j in trees.query(r["g"]):
                    c = isos[j]
                    if c != iso and length_km(r["g"].intersection(C[c].buffer(0.03))) >= 25: thr.append(c)
                orv["through"] = sorted(thr)
                ends = [Point(main.coords[0]), Point(main.coords[-1])]
                d = [coast.distance(e) * 111 for e in ends]
                if min(d) < 40 and max(d) > 120: orv["mouth"] = 0 if d[0] < d[1] else 1
            o["river"] = orv
        if o: out[iso] = o
    try: targets = list(json.load(open("country-data.json", encoding="utf-8")).keys())
    except Exception: targets = [k for k in out if isinstance(out[k], dict)]
    wikidata_fill(out, C, coast, targets)
    for iso_, v_ in over.items():   # hand-sourced rivers and lakes (including {"none":1} for countries with no permanent major one)
        for k_ in ("river", "lake"):
            if isinstance(v_, dict) and k_ in v_: out.setdefault(iso_, {})[k_] = v_[k_]
    try: LO = json.load(open("lake_outlines.json", encoding="utf-8"))
    except Exception: LO = {}
    for iso_, rings in LO.items():   # real outlines for hand-sourced lakes (fetch_lake_outlines.py)
        lk_ = (out.get(iso_) or {}).get("lake")
        if lk_ and not lk_.get("none") and not lk_.get("poly"): lk_["poly"] = rings
    lk = {l["n"]: l for l in L}
    out["_ref"] = {"river": max(({"n": v["river"]["n"], "km": int(round(v["river"]["km"], -1))} for k, v in out.items() if isinstance(v, dict) and v.get("river") and not v["river"].get("approx")), key=lambda r: r["km"]),
                   "lakes": [{"n": n, "km2": int(round(lk[n]["a"]))} for n in ("Windermere", "Geneva", "Superior", "Victoria") if n in lk]}
    json.dump(out, open("geography.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("countries:", len(out) - 1, "bytes:", os.path.getsize("geography.json"))

if __name__ == "__main__":
    main()
