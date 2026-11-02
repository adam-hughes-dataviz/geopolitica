"""Collect trade in services by category into services.json.
Main source: IMF balance of payments (BPM6), through DBnomics. Countries the IMF has no figures for use the OECD-WTO BaTIS
modelled estimates (12 headline categories). No keys needed. Runs monthly on GitHub Actions."""
import csv, io, json, os, re, sys, time, urllib.parse, urllib.request, urllib.error

DB = "https://api.db.nomics.world/v22/series/IMF/BOP"
SDMX = "https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,DSD_BATIS@DF_BATIS,1.0/"
UA = {"User-Agent": "geopolitica-dashboard/1.0 (https://github.com/adam-hughes-dataviz/geopolitica)"}
MIN_YEAR = 2015   # an IMF series that stops before this is treated as no data

# key -> (name shown on the page, IMF indicator stem; BX<stem>_BP6_USD is exports, BM<stem>_BP6_USD imports)
LEAF = {
    "manuf": ("Manufacturing services", "SM"), "repair": ("Maintenance and repair", "SR"),
    "sea": ("Sea transport", "STRS"), "air": ("Air transport", "STRA"), "oth": ("Other modes of transport", "STROT"), "post": ("Postal and courier", "STRPC"),
    "tvb": ("Business travel", "STVB"), "tvp": ("Personal travel and holidays", "STVPO"), "tvh": ("Health-related travel", "STVPH"), "tve": ("Education-related travel", "STVPED"),
    "cons": ("Construction", "SOCN"), "ins": ("Insurance", "SOIN"), "pens": ("Pension and guarantee services", "SOINPG"), "fin": ("Financial services", "SOFI"),
    "ip": ("Intellectual property charges", "SORL"),
    "tel": ("Telecommunications", "SOTCMT"), "comp": ("Computer services", "SOTCMC"), "info": ("Information services", "SOTCMM"),
    "rd": ("Research and development", "SOOBRD"), "prof": ("Professional and management consulting", "SOOBPM"), "tech": ("Technical, trade-related and other business", "SOOBTT"),
    "av": ("Film, TV and music", "SOPCRAU"), "pcro": ("Other personal, cultural and recreational", "SOPCRO"), "gov": ("Government services", "SOGGS"),
}
# group fallbacks: when a country gives a group's total but none of its parts, the total is shown under the group's own name
GROUP = {
    "trn": ("Transport", "STR", ["sea", "air", "oth", "post"]), "trv": ("Travel", "STV", ["tvb", "tvp", "tvh", "tve"]),
    "insg": ("Insurance and pensions", "SOIN", ["ins", "pens"]), "tci": ("Telecoms, computing and information", "SOTCM", ["tel", "comp", "info"]),
    "ob": ("Other business services", "SOOB", ["rd", "prof", "tech"]), "pcr": ("Personal, cultural and recreational", "SOPCR", ["av", "pcro"]),
}
SINGLE = ["manuf", "repair", "cons", "fin", "ip", "gov"]
# BaTIS service codes -> keys (12 headline categories)
BATIS = {"SA": "manuf", "SB": "repair", "SC": "trn", "SD": "trv", "SE": "cons", "SF": "insg", "SG": "fin", "SH": "ip", "SI": "tci", "SJ": "ob", "SK": "pcr", "SL": "gov"}

DEADLINE = time.time() + 40 * 60
class Out(BaseException): pass

def http(url, accept="application/json", tries=3):
    if time.time() > DEADLINE: raise Out()
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=dict(UA, Accept=accept))
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (400, 404, 413): return None
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    return None

def codes():
    keys = []
    try:
        for k in json.load(open("country-data.json", encoding="utf-8")).keys():
            keys.append(k)
    except Exception:
        for line in open("codes.txt", encoding="utf-8"):
            k = line.split(" ", 1)[0].strip()
            if re.fullmatch(r"[A-Z]{3}", k) and k not in keys: keys.append(k)
    return keys

def iso2(k):
    import pycountry
    c = pycountry.countries.get(alpha_3=k)
    return c.alpha_2 if c else None

def all_codes():
    stems = ["S"] + [v[1] for v in LEAF.values()] + [g[1] for g in GROUP.values()]
    out = []
    for s in sorted(set(stems)):
        out += ["BX%s_BP6_USD" % s, "BM%s_BP6_USD" % s]
    return out

def imf_series(c2):
    """{indicator: {year: value}} for one country, annual."""
    got = {}
    cs = all_codes()
    for i in range(0, len(cs), 50):
        q = urllib.parse.urlencode({"dimensions": json.dumps({"FREQ": ["A"], "REF_AREA": [c2], "INDICATOR": cs[i:i + 50]}), "limit": 1000, "observations": 1})
        t = http("%s?%s" % (DB, q)); time.sleep(1)
        try: docs = json.loads(t)["series"]["docs"]
        except Exception: continue
        for s in docs:
            ind = s.get("dimensions", {}).get("INDICATOR")
            pts = {p[:4]: v for p, v in zip(s.get("period") or [], s.get("value") or []) if isinstance(v, (int, float))}
            if ind and pts: got[ind] = pts
    return got

def leaves(get, side):
    """get(stem) -> value or None. Returns {key: value} using the finest level the country reports."""
    out = {}
    for k in SINGLE:
        v = get(LEAF[k][1])
        if v and v > 0: out[k] = v
    for g, (name, stem, kids) in GROUP.items():
        vals = {k: get(LEAF[k][1]) for k in kids}
        if g == "trv":   # personal travel: use the "other" part, or the personal total less health and education
            if not vals["tvp"]:
                p = get("STVP")
                if p: vals["tvp"] = p - (vals["tvh"] or 0) - (vals["tve"] or 0)
        if g == "insg" and vals["pens"] and vals["ins"]:
            vals["ins"] = vals["ins"] - vals["pens"]
        got = {k: v for k, v in vals.items() if v and v > 0}
        if got:
            out.update(got)
        else:
            t = get(stem)
            if t and t > 0: out[g] = t
    return out

def imf_country(k):
    c2 = iso2(k)
    if not c2: return None
    s = imf_series(c2)
    xs, ms = s.get("BXS_BP6_USD") or {}, s.get("BMS_BP6_USD") or {}
    years = sorted(set(xs) & set(ms))
    if not years or years[-1] < str(MIN_YEAR): return None
    y = years[-1]
    gx = lambda stem: (s.get("BX%s_BP6_USD" % stem) or {}).get(y)
    gm = lambda stem: (s.get("BM%s_BP6_USD" % stem) or {}).get(y)
    return {"y": int(y), "src": "imf", "xt": xs[y], "mt": ms[y], "x": leaves(gx, "x"), "m": leaves(gm, "m")}

def rescale(data, wb):
    """IMF values are in millions of US dollars; confirm against the World Bank total already collected, and scale."""
    ratios = []
    for k, d in data.items():
        w = (wb.get(k) or {}).get("sx")
        if d.get("src") == "imf" and w and w[0] and d["xt"]:
            ratios.append(w[0] / d["xt"])
    ratios.sort()
    r = ratios[len(ratios) // 2] if ratios else 1e6
    best = min((1, 1e3, 1e6, 1e9), key=lambda m: abs(__import__("math").log10(r / m)))
    print("IMF unit check: median World Bank / IMF ratio =", round(r), "-> scale", best, "from", len(ratios), "countries")
    for d in data.values():
        if d.get("src") != "imf": continue
        d["xt"] *= best; d["mt"] *= best
        for side in ("x", "m"):
            d[side] = {k: v * best for k, v in d[side].items()}
    return data

def batis_country(k):
    """Modelled OECD-WTO BaTIS estimates for one country: totals to the whole world, 12 headline categories."""
    for cp in ("W", "WLD", "WORLD", "_T"):
        key = "%s.%s......" % (k, cp)
        t = http(SDMX + key + "?startPeriod=2018&format=csvfilewithlabels", "text/csv"); time.sleep(3)
        if not t: continue
        rows = list(csv.DictReader(io.StringIO(t)))
        if not rows: continue
        print("batis", k, "counterpart", cp, "rows", len(rows), "columns", list(rows[0].keys())[:14])
        def col(r, *names):
            for n in names:
                for c in r:
                    if c.upper().startswith(n): return c
        cS, cF, cV, cT, cU, cM = (col(rows[0], "SERVICE"), col(rows[0], "TRADE_FLOW"), col(rows[0], "OBS_VALUE"), col(rows[0], "TIME_PERIOD"), col(rows[0], "UNIT_MEASURE"), col(rows[0], "UNIT_MULT"))
        print("  distinct units:", sorted(set(r.get(cU, "") for r in rows))[:6], "flows:", sorted(set(r.get(cF, "") for r in rows))[:6])
        usd = [r for r in rows if "USD" in (r.get(cU) or "").upper() or "DOLLAR" in (r.get(cU) or "").upper()] or rows
        yrs = sorted(set(r[cT] for r in usd if r.get(cV)))
        if not yrs: continue
        y = yrs[-1]
        side = {"x": {}, "m": {}}
        tot = {"x": 0, "m": 0}
        for r in usd:
            if r[cT] != y or not r.get(cV): continue
            fl = (r.get(cF) or "").upper()
            sd = "x" if fl.startswith(("X", "EXP")) else "m" if fl.startswith(("M", "IMP")) else None
            if not sd: continue
            try: v = float(r[cV]) * 10 ** int(float(r.get(cM) or 0))
            except Exception: continue
            code = (r.get(cS) or "").split(":")[0].strip()
            if code == "S": tot[sd] = v
            elif code in BATIS and v > 0: side[sd][BATIS[code]] = v
        if tot["x"] and tot["m"]:
            return {"y": int(y[:4]), "src": "batis", "xt": tot["x"], "mt": tot["m"], "x": side["x"], "m": side["m"]}
    return None

def main():
    try: data = json.load(open("services.json", encoding="utf-8"))
    except Exception: data = {}
    try: wb = json.load(open("indicators.json", encoding="utf-8"))
    except Exception: wb = {}
    ks = codes()
    try:
      for n, k in enumerate(ks, 1):
        if n % 10 == 1: print("progress", n, "of", len(ks), flush=True)
        d = imf_country(k)
        if d: data[k] = d; print("imf", k, d["y"], len(d["x"]), len(d["m"]), flush=True)
        else: data[k] = {"src": "none"}; print("no imf data", k, flush=True)
    except Out:
      print("TIME CAP reached before all countries were fetched; saving what we have", flush=True)
    for k in ks: data.setdefault(k, {"src": "none"})
    data = rescale(data, wb)
    for k in ks:
      try:
        if data[k].get("src") == "none":
            d = batis_country(k)
            if d: data[k] = d; print("batis", k, d["y"], len(d["x"]), len(d["m"]))
            else: print("STILL MISSING services (need a source from you):", k)
      except Out:
        print("TIME CAP reached during BaTIS; saving", flush=True); break
    json.dump(data, open("services.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("services.json countries:", len(data))

if __name__ == "__main__":
    main()
