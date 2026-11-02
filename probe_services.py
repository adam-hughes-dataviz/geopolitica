"""One-off probe: which detailed services areas (EBOPS 2010) can be fetched, and for how many countries.
Prints a compact report only. Writes nothing to the repo."""
import json, re, sys, time, urllib.request, urllib.parse

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "geopolitica-probe"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            print("  HTTP", e.code, url[:150])
            if e.code in (400, 404):
                return None
            time.sleep(3)
        except Exception as e:
            print("  ERR", type(e).__name__, str(e)[:80], url[:120]); time.sleep(3)
    return None

DB = "https://api.db.nomics.world/v22"
SAMPLE = ["GBR", "CRI", "DEU", "USA", "IND", "BGD", "ERI", "BLR", "AFG", "ALB", "AGO", "ARG"]

print("=== 1. IMF datasets on DBnomics that mention balance of payments ===")
j = get(DB + "/datasets/IMF?limit=1000")
cands = []
for d in ((j or {}).get("datasets", {}).get("docs") or (j or {}).get("datasets") or []):
    code, name = d.get("code"), d.get("name", "")
    if re.search(r"balance of payments|BOP|international trade in services|ITS", code + " " + name, re.I):
        cands.append(code); print(" ", code, "|", name)

print("\n=== 2. Dimensions of the main BOP dataset ===")
ds = "BOP" if "BOP" in cands else (cands[0] if cands else "BOP")
meta = get("%s/datasets/IMF/%s?limit=1&offset=0&observations=0" % (DB, ds))
doc = ((meta or {}).get("datasets", {}).get("docs") or [{}])[0] if meta else {}
order = doc.get("dimensions_codes_order") or []
labels = doc.get("dimensions_values_labels") or {}
codes = doc.get("dimensions_codes") or {}
print("dataset", ds, "| dimension order:", order)
for dim in order:
    vals = codes.get(dim) or []
    print("  %s: %d values, first few: %s" % (dim, len(vals), vals[:6]))

print("\n=== 3. Indicator codes that look like services ===")
ind_dim = next((d for d in order if re.search(r"indicator|item|account", d, re.I)), None)
svc = []
if ind_dim:
    lab = labels.get(ind_dim) or {}
    for c in codes.get(ind_dim, []):
        l = lab.get(c, "") if isinstance(lab, dict) else ""
        if re.search(r"service|transport|travel|constru|insurance|financ|telecom|computer|royalt|intellectual|licen|maint|repair|government", l, re.I):
            svc.append((c, l))
    print("indicator dimension:", ind_dim, "| services-like indicators:", len(svc))
    for c, l in svc[:120]:
        print("  ", c, "|", l[:110])

print("\n=== 4. Coverage for sample countries (annual, credit side if found) ===")
iso2 = {}
try:
    import pycountry
    for k in SAMPLE:
        iso2[k] = pycountry.countries.get(alpha_3=k).alpha_2
except Exception:
    iso2 = {"GBR": "GB", "CRI": "CR", "DEU": "DE", "USA": "US", "IND": "IN", "BGD": "BD", "ERI": "ER", "BLR": "BY", "AFG": "AF", "ALB": "AL", "AGO": "AO", "ARG": "AR"}
area_dim = next((d for d in order if re.search(r"ref_area|country|area", d, re.I)), None)
print("country dimension:", area_dim, "| sample values:", (codes.get(area_dim) or [])[:5])
if area_dim and ind_dim:
    for k, c2 in iso2.items():
        for cc in (c2, k):
            if cc in (codes.get(area_dim) or []):
                q = urllib.parse.urlencode({"dimensions": json.dumps({area_dim: [cc]}), "limit": 1000, "observations": 1})
                j = get("%s/series/IMF/%s?%s" % (DB, ds, q))
                docs = (j or {}).get("series", {}).get("docs") or []
                hits = {}
                for s in docs:
                    d = s.get("dimensions", {})
                    ic = d.get(ind_dim)
                    if any(ic == c for c, _ in svc) and str(s.get("@frequency") or d.get("FREQ") or "").upper().startswith("A"):
                        per, val = s.get("period") or [], s.get("value") or []
                        got = [(p, v) for p, v in zip(per, val) if isinstance(v, (int, float))]
                        if got: hits[ic] = got[-1][0]
                print(k, cc, "| series returned:", len(docs), "| services series with annual data:", len(hits), "| latest years:", sorted(set(hits.values()))[-3:])
                break
        else:
            print(k, "country code not in dataset")

print("\n=== 5. UN Comtrade services (EBOPS) probe ===")
for path in ("public/v1/preview/S/A/EB02", "public/v1/preview/S/A/EB10"):
    j = get("https://comtradeapi.un.org/%s?reporterCode=826&period=2022&flowCode=X&maxRecords=100&includeDesc=true" % path)
    rows = (j or {}).get("data") or []
    print(path, "rows:", len(rows), [ (r.get("cmdCode"), r.get("cmdDesc"), r.get("primaryValue")) for r in rows[:8]])
print("\nprobe finished")
