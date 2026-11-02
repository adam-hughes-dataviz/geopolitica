"""Probe 2: list the IMF balance of payments services indicators (credit and debit, US dollars) and check
which countries report each one. Prints a report only. Writes nothing to the repo."""
import json, re, time, urllib.request, urllib.parse

DB = "https://api.db.nomics.world/v22"
SAMPLE = {"GBR": "GB", "CRI": "CR", "DEU": "DE", "USA": "US", "IND": "IN", "BGD": "BD", "ERI": "ER", "BLR": "BY", "AFG": "AF", "ALB": "AL", "AGO": "AO", "ARG": "AR", "CUB": "CU", "TCD": "TD", "GNQ": "GQ"}

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "geopolitica-probe"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            try: body = e.read()[:200].decode("utf-8", "replace")
            except Exception: body = ""
            print("  HTTP", e.code, url[:140], "|", body)
            if e.code in (400, 404): return None
            time.sleep(5)
        except Exception as e:
            print("  ERR", type(e).__name__, str(e)[:80]); time.sleep(5)
    return None

meta = get("%s/series/IMF/BOP?limit=1&offset=0" % DB)
lab = ((meta or {}).get("dataset") or {}).get("dimensions_values_labels", {}).get("INDICATOR", {})
print("indicator labels loaded:", len(lab))

print("\n=== A. Services indicators, US dollars, credit (exports) and debit (imports) ===")
pat = re.compile(r"^(Current Account, )?(Goods and Services, )?Services,? ", re.I)
svc = {}
for c, l in lab.items():
    if not c.endswith("_USD"):
        continue
    if l.startswith("Current Account, Goods and Services, Services,") and "Special Purpose" not in l and re.search(r"Credit|Debit", l):
        svc[c] = l
for c in sorted(svc):
    print(" ", c, "|", svc[c][:150])
print("count:", len(svc))

print("\n=== B. Which of those have annual data per sample country (latest year, 2015 onwards) ===")
codes = sorted(svc)
res = {}
for k, c2 in SAMPLE.items():
    got = {}
    for i in range(0, len(codes), 50):
        chunk = codes[i:i + 50]
        q = urllib.parse.urlencode({"dimensions": json.dumps({"FREQ": ["A"], "REF_AREA": [c2], "INDICATOR": chunk}), "limit": 1000, "observations": 1})
        time.sleep(1)
        j = get("%s/series/IMF/BOP?%s" % (DB, q))
        for s in ((j or {}).get("series") or {}).get("docs") or []:
            per, val = s.get("period") or [], s.get("value") or []
            pts = [(p, v) for p, v in zip(per, val) if isinstance(v, (int, float))]
            if pts and pts[-1][0] >= "2015":
                got[s["dimensions"]["INDICATOR"]] = pts[-1][0]
    res[k] = got
    print(k, c2, "| indicators with data since 2015:", len(got), "| latest years:", sorted(set(got.values()))[-3:])

print("\n=== C. Per indicator: how many of the sample countries report it (credit side only) ===")
for c in codes:
    if "Credit" not in svc[c]:
        continue
    n = [k for k in SAMPLE if c in res.get(k, {})]
    print("%2d/%d %s | %s" % (len(n), len(SAMPLE), c, svc[c][:110]))

print("\n=== D. Full list for CRI and ERI (credit side) ===")
for k in ("CRI", "ERI"):
    print(k, sorted((c, y) for c, y in res.get(k, {}).items() if "Credit" in svc[c]))
print("\n=== E. OECD-WTO BaTIS on the OECD SDMX API (fallback for countries with no official data) ===")
def raw(url, accept="application/xml"):
    for i in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "geopolitica-probe", "Accept": accept})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            try: body = e.read()[:200].decode("utf-8", "replace")
            except Exception: body = ""
            print("  HTTP", e.code, url[:150], "|", body); 
            if e.code in (400, 404): return None
            time.sleep(10)
        except Exception as e:
            print("  ERR", type(e).__name__, str(e)[:80]); time.sleep(5)
    return None
x = raw("https://sdmx.oecd.org/public/rest/dataflow/OECD.SDD.TPS/all")
flows = re.findall(r'<structure:Dataflow[^>]*id="([^"]+)"[^>]*version="([^"]+)"[^>]*>.*?<common:Name xml:lang="en">([^<]*)', x or "", re.S)
bat = [f for f in flows if re.search(r"BATIS", f[0] + f[2], re.I)]
print("dataflows mentioning BATIS:", bat)
for fid, ver, name in bat[:3]:
    st = raw("https://sdmx.oecd.org/public/rest/dataflow/OECD.SDD.TPS/%s/%s?references=all" % (fid, ver))
    dims = re.findall(r'<structure:Dimension [^>]*id="([^"]+)"', st or "")
    print("flow", fid, ver, "| dimensions in order:", dims)
    if not dims:
        continue
    for k, c3 in (("ERI", "ERI"), ("CUB", "CUB"), ("TCD", "TCD"), ("GNQ", "GNQ"), ("CRI", "CRI")):
        for area in [d for d in dims if re.search(r"REF_AREA|REPORTER|COUNTRY", d)][:1]:
            key = ".".join(c3 if d == area else "" for d in dims)
            t = raw("https://sdmx.oecd.org/public/rest/data/OECD.SDD.TPS,%s,%s/%s?lastNObservations=1&format=csvfilewithlabels" % (fid, ver, key), "text/csv")
            lines = (t or "").splitlines()
            print(k, "key", key, "| rows:", max(len(lines) - 1, 0))
            if k in ("ERI", "CRI"):
                for ln in lines[:3]: print("   ", ln[:400])
            time.sleep(3)
    break
print("\nprobe finished")
