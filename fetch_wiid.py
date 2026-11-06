"""Pull Gini candidates from UNU-WIDER WIID (and the WIID Companion) for countries the World Bank lacks.
Writes wiid_candidates.json: every entry since 2000 for the target countries, with survey, concept and quality fields, for review."""
import io, json, sys, urllib.request
import pandas as pd
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Referer": "https://www.wider.unu.edu/database/world-income-inequality-database-wiid", "Accept": "*/*"}
FILES = {"wiid": "https://www.wider.unu.edu/sites/default/files/WIID/WIID-08SEP2026.xlsx",
         "companion": "https://www.wider.unu.edu/sites/default/files/WIID/wiidcountry_7.xlsx"}
TARGETS = {"AFG", "AND", "ATG", "BHR", "BRN", "KHM", "CUB", "ERI", "BHS", "DMA"}
out = {}
for name, url in FILES.items():
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read()
        df = pd.read_excel(io.BytesIO(raw), sheet_name=0)
    except Exception as e:
        print(name, "FAILED", e); continue
    print(name, "rows", len(df), "columns", list(df.columns), flush=True)
    c3 = next((c for c in df.columns if str(c).lower() in ("c3", "iso3", "country_code3")), None)
    if not c3: print(name, "no iso3 column"); continue
    sub = df[df[c3].isin(TARGETS)]
    yc = next((c for c in df.columns if str(c).lower() == "year"), None)
    if yc is not None: sub = sub[sub[yc] >= 2000]
    out[name] = json.loads(sub.to_json(orient="records"))
    print(name, "target rows", len(sub), flush=True)
json.dump(out, open("wiid_candidates.json", "w"), ensure_ascii=False, indent=0)

# gini_extra.json: for countries the World Bank has no Gini for. Rule: latest WIID entry with a Gini, quality High or Average,
# year 2005 or later. DENY lists entries that meet the rule but measure something not comparable. Everything else is "no official estimate".
DENY = {"BHR": "WIID entry is per-capita income across a population with a large migrant workforce; not comparable"}
SRC = {"National statistical authority": "national statistics office", "World Bank": "World Bank estimate", "Research study": "research study"}
extra = {}
for iso in sorted(TARGETS):
    rows = [r for r in out.get("wiid", []) if r.get("c3") == iso and r.get("gini") is not None and r.get("quality") in ("High", "Average") and r.get("year", 0) >= 2005]
    if iso in DENY or not rows:
        extra[iso] = {"none": True, "why": DENY.get(iso, "no qualifying entry in WIID")}; continue
    r = max(rows, key=lambda x: (x["year"], x.get("quality_score") or 0))
    extra[iso] = {"v": round(float(r["gini"]), 1), "y": int(r["year"]), "basis": (r.get("resource") or "").lower(), "src": "UNU-WIDER WIID (%s%s)" % (SRC.get(r.get("source"), r.get("source")), ", " + r["source_detailed"] if r.get("source_detailed") and r.get("source") == "Research study" else ""), "survey": r.get("survey") or ""}
import os
if os.path.exists("gini_manual.json"): extra.update(json.load(open("gini_manual.json", encoding="utf-8")))   # hand-sourced entries win
json.dump(extra, open("gini_extra.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(extra, ensure_ascii=False))
