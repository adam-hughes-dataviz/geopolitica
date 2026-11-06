"""Reads each legislature's Wikipedia infobox (seats by party with colours, opposition leader) -> parliaments_raw.json for review."""
import json, re, time, urllib.request, urllib.parse
from bs4 import BeautifulSoup
UA = {"User-Agent": "geopolitica-dashboard/1.0 (https://github.com/adam-hughes-dataviz/geopolitica)"}
T = {
"ALB":"Parliament of Albania","AND":"General Council (Andorra)","AGO":"National Assembly (Angola)","ATG":"House of Representatives (Antigua and Barbuda)","ARG":"Argentine Chamber of Deputies","ARM":"National Assembly (Armenia)","AUS":"Australian House of Representatives","AUT":"National Council (Austria)","AZE":"National Assembly (Azerbaijan)","BHS":"House of Assembly of the Bahamas","BHR":"Council of Representatives (Bahrain)","BGD":"Jatiya Sangsad","BRB":"House of Assembly of Barbados","BLR":"House of Representatives (Belarus)","BEL":"Chamber of Representatives (Belgium)","BLZ":"House of Representatives of Belize","BEN":"National Assembly (Benin)","BTN":"National Assembly of Bhutan","BOL":"Chamber of Deputies (Bolivia)","BIH":"House of Representatives of Bosnia and Herzegovina","BWA":"National Assembly of Botswana","BRA":"Chamber of Deputies (Brazil)","BRN":"Legislative Council of Brunei","BGR":"National Assembly (Bulgaria)","BFA":"Transitional Legislative Assembly of Burkina Faso","BDI":"National Assembly (Burundi)","CPV":"National Assembly (Cape Verde)","KHM":"National Assembly (Cambodia)","CMR":"National Assembly (Cameroon)","CAN":"House of Commons of Canada","CAF":"National Assembly (Central African Republic)","TCD":"National Assembly (Chad)","CHL":"Chamber of Deputies of Chile","CHN":"National People's Congress","COL":"Chamber of Representatives of Colombia","COM":"Assembly of the Union of the Comoros","COD":"National Assembly (Democratic Republic of the Congo)","COG":"National Assembly (Republic of the Congo)","CRI":"Legislative Assembly of Costa Rica","CIV":"National Assembly (Ivory Coast)","HRV":"Croatian Parliament","CUB":"National Assembly of People's Power","CYP":"House of Representatives (Cyprus)","CZE":"Chamber of Deputies of the Czech Republic","DNK":"Folketing","DJI":"National Assembly (Djibouti)","DMA":"House of Assembly of Dominica","DOM":"Chamber of Deputies of the Dominican Republic","ECU":"National Assembly (Ecuador)","EGY":"House of Representatives (Egypt)","SLV":"Legislative Assembly of El Salvador","GNQ":"Chamber of Deputies (Equatorial Guinea)","ERI":"National Assembly (Eritrea)","EST":"Riigikogu","SWZ":"House of Assembly of Eswatini","ETH":"House of Peoples' Representatives","FJI":"Parliament of Fiji","FIN":"Parliament of Finland","FRA":"National Assembly (France)","GBR":"House of Commons of the United Kingdom","DZA":"People's National Assembly"}
def html_groups(title):
    u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "parse", "page": title, "prop": "text", "format": "json", "redirects": 1, "formatversion": 2})
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r: h = json.load(r)["parse"]["text"]
    except Exception as e: return {"html_error": str(e)}
    s = BeautifulSoup(h, "html.parser"); ib = s.find("table", class_=re.compile("infobox"))
    if not ib: return {"groups": []}
    groups = []; opp = []
    for tr in ib.find_all("tr"):
        th = tr.find("th"); lab = th.get_text(" ", strip=True) if th else ""
        if re.search(r"opposition", lab, re.I): opp.append(lab + ": " + (tr.find("td").get_text(" ", strip=True) if tr.find("td") else ""))
        if re.search(r"political groups|composition|seat", lab, re.I) or not th:
            td = tr.find("td")
            if not td: continue
            for li in td.find_all("li"):
                if li.find_parent("li") and li.find_parent("li") is not li: continue
                sp = li.find(lambda x: x.name in ("span", "div") and "background" in (x.get("style") or ""))
                m = re.search(r"background(?:-color)?:\s*([^;\"]+)", sp.get("style")) if sp else None
                for sup in li.find_all("sup"): sup.decompose()
                txt = li.get_text(" ", strip=True)
                a = li.find("a"); groups.append({"c": m.group(1).strip() if m else None, "t": txt, "a": (a.get("title") if a else None)})
            heads = [x.get_text(" ", strip=True) for x in td.find_all(["b", "dt", "strong"])]
            if heads: groups.append({"heads": heads})
    sm = re.search(r"Seats\s*([0-9,]+)", ib.get_text(" ", strip=True))
    return {"groups": groups, "opp": opp, "seats_ib": sm.group(1) if sm else None}

out = {}
for iso, t in T.items():
    u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "parse", "page": t, "prop": "wikitext", "format": "json", "redirects": 1, "formatversion": 2})
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r: w = json.load(r)["parse"]["wikitext"]
    except Exception as e: out[iso] = {"title": t, "error": str(e)}; continue
    i = w.lower().find("{{infobox"); d = 0; j = i
    while j < len(w):
        if w.startswith("{{", j): d += 1; j += 2
        elif w.startswith("}}", j):
            d -= 1; j += 2
            if d == 0: break
        else: j += 1
    ib = w[i:j] if i >= 0 else ""
    keep = [l for l in ib.split("\n") if re.match(r"\s*\|\s*(seats|house|term|leader|party|political|structure|composition|opposition|government|lower|upper|members|speaker|prime|president|chair)", l, re.I) or "{{" in l and ("%" in l or "#" in l)]
    out[iso] = {"title": t, "len": len(w), "infobox": ib[:2500], "lines": keep[:40], **html_groups(t)}
    time.sleep(0.5)
json.dump(out, open("parliaments_raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def leader_of(title):
    u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "parse", "page": title, "prop": "text", "format": "json", "redirects": 1, "formatversion": 2})
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r: h = json.load(r)["parse"]["text"]
    except Exception: return None
    s = BeautifulSoup(h, "html.parser"); ib = s.find("table", class_=re.compile("infobox"))
    if not ib: return None
    for tr in ib.find_all("tr"):
        th = tr.find("th")
        if th and re.match(r"(party )?(leader|chair|president)", th.get_text(" ", strip=True), re.I) and tr.find("td"):
            return re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", "", tr.find("td").get_text(" ", strip=True))).strip()
    return None

res = {}
for iso, v in out.items():
    if "error" in v or "html_error" in v: res[iso] = {"status": "fetch failed"}; continue
    gs = [g for g in v["groups"] if "c" in g and re.search(r"\(\s*\d+\s*\)\s*$", g["t"]) and not g["t"].startswith("^")]
    heads = [h for g in v["groups"] if "heads" in g for h in g["heads"]]
    rows = []
    for g in gs:
        m = re.match(r"(.*?)\s*\(\s*(\d+)\s*\)\s*$", g["t"]); rows.append({"n": m.group(1).strip(), "s": int(m.group(2)), "c": g["c"], "a": g["a"]})
    tot = sum(r["s"] for r in rows)
    gov = None
    for h in heads:
        m = re.match(r"(?:The )?Government.*\((\d+)\)\s*$", h)
        if m: gov = int(m.group(1))
    acc = 0
    for r in rows:
        r["gov"] = bool(gov) and acc < gov; acc += r["s"]
    opp_party = next((r for r in rows if gov and not r["gov"] and not re.match(r"(independent|non-attached|vacan|others?)", r["n"], re.I)), None)
    res[iso] = {"status": "ok" if rows else "no table", "seats_ib": v.get("seats_ib"), "sum": tot, "gov_total": gov, "heads": heads, "rows": rows, "opp_office": v.get("opp"),
                "opp_party_leader": (opp_party["n"], leader_of(opp_party["a"]) if opp_party and opp_party["a"] else None) if opp_party else None}
    time.sleep(0.5)
json.dump(res, open("parliaments.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(sum(1 for v in res.values() if v["status"] == "ok"), "tables")
