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
    if re.match(r"^(Goods and )?Services, (Credit|Debit)", l) or re.match(r"^Current Account, Goods and Services, Services, (Credit|Debit)", l):
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
print("\nprobe finished")
