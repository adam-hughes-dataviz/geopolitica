"""Build geography.json: area, highest and lowest points, biggest river and biggest lake per country.
Sources (all free, public): CIA World Factbook (github.com/factbook/factbook.json) for area and elevation,
Natural Earth (github.com/nvkelso/natural-earth-vector) for river and lake shapes, lengths and areas.
Run monthly on GitHub Actions. Nothing here is typed by hand except the short geo_overrides.json list."""
import csv, difflib, glob, html, json, math, os, re, sys, time, unicodedata, urllib.request
import numpy as np
from shapely.geometry import shape, mapping, MultiLineString, LineString, Point
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
    coast = unary_union([shape(f["geometry"]) for f in land["features"]]).boundary
    # ---- lakes (Natural Earth shapes; same-name pieces merged, area from the merged outline)
    pieces = {}
    for f in lakes["features"]:
        p = f["properties"]; n = p.get("name_en") or p.get("name")
        if not n: continue
        g = shape(f["geometry"])
        if not g.is_empty: pieces.setdefault(n, []).append(g)
    L = []
    for n, gs in pieces.items():
        g = unary_union(gs)
        sh = {}
        for i in trees.query(g):
            inter = g.intersection(C[isos[i]])
            if not inter.is_empty and inter.area / g.area >= 0.05: sh[isos[i]] = inter.area / g.area
        L.append({"n": n, "a": area_km2(g) if g.geom_type == "Polygon" else sum(area_km2(x) for x in g.geoms), "g": g, "sh": sh, "k": norm(n)})
    ltree = STRtree([l["g"] for l in L])
    Lk = {}
    for l in L: Lk.setdefault(l["k"], []).append(l)
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
        if lake:
            ol = {"n": lake["n"], "km2": lake["km2"], "shared": lake["shared"]}
            if lake.get("approx"): ol["approx"] = 1
            if lake["shp"]:
                g = lake["shp"]["g"].simplify(0.01)
                polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g]
                ol["poly"] = [rd(p.exterior.coords, 3) for p in sorted(polys, key=lambda p: -p.area)[:4]]
            o["lake"] = ol
        # ---- biggest river: Factbook (longest not shared, else longest), shape matched by name; else longest on the map
        allin = []
        for i in rtree.query(cg):
            r = RIV[i]; ins = r["g"].intersection(cg); li = length_km(ins)
            if li >= 25: allin.append((li, r, ins))
        allin.sort(key=lambda t: -t[0])
        fr = parse_rivers(f); pick = None; shp = None
        if fr:
            pool = [x for x in fr if not x["shared"]] or fr
            pick = max(pool, key=lambda x: x["km"])
            for nm in pick["names"]:
                for li, r, ins in allin:
                    if r["k"] == norm(nm) and (shp is None or li > shp[0]): shp = (li, r, ins)
        elif allin:
            shp = allin[0]
        if pick or shp:
            if pick: name, km, approx = (pick["names"][1] if len(pick["names"]) > 1 else pick["names"][0]), pick["km"], False
            else: name, km, approx = shp[1]["n"], int(round(shp[1]["km"], -1)), True
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
    lk = {l["n"]: l for l in L}
    out["_ref"] = {"river": max(({"n": v["river"]["n"], "km": int(round(v["river"]["km"], -1))} for k, v in out.items() if isinstance(v, dict) and v.get("river") and not v["river"].get("approx")), key=lambda r: r["km"]),
                   "lakes": [{"n": n, "km2": int(round(lk[n]["a"]))} for n in ("Windermere", "Geneva", "Superior", "Victoria") if n in lk]}
    json.dump(out, open("geography.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("countries:", len(out) - 1, "bytes:", os.path.getsize("geography.json"))

if __name__ == "__main__":
    main()
