"""Reads each legislature's Wikipedia infobox (seats by party with colours, opposition leader) -> parliaments_raw.json for review."""
import json, re, time, urllib.request, urllib.parse
UA = {"User-Agent": "geopolitica-dashboard/1.0 (https://github.com/adam-hughes-dataviz/geopolitica)"}
T = {
"ALB":"Parliament of Albania","AND":"General Council (Andorra)","AGO":"National Assembly (Angola)","ATG":"House of Representatives (Antigua and Barbuda)","ARG":"Argentine Chamber of Deputies","ARM":"National Assembly (Armenia)","AUS":"Australian House of Representatives","AUT":"National Council (Austria)","AZE":"National Assembly (Azerbaijan)","BHS":"House of Assembly of the Bahamas","BHR":"Council of Representatives (Bahrain)","BGD":"Jatiya Sangsad","BRB":"House of Assembly of Barbados","BLR":"House of Representatives (Belarus)","BEL":"Chamber of Representatives (Belgium)","BLZ":"House of Representatives of Belize","BEN":"National Assembly (Benin)","BTN":"National Assembly of Bhutan","BOL":"Chamber of Deputies (Bolivia)","BIH":"House of Representatives of Bosnia and Herzegovina","BWA":"National Assembly of Botswana","BRA":"Chamber of Deputies (Brazil)","BRN":"Legislative Council of Brunei","BGR":"National Assembly (Bulgaria)","BFA":"Transitional Legislative Assembly of Burkina Faso","BDI":"National Assembly (Burundi)","CPV":"National Assembly (Cape Verde)","KHM":"National Assembly (Cambodia)","CMR":"National Assembly (Cameroon)","CAN":"House of Commons of Canada","CAF":"National Assembly (Central African Republic)","TCD":"National Assembly (Chad)","CHL":"Chamber of Deputies of Chile","CHN":"National People's Congress","COL":"Chamber of Representatives of Colombia","COM":"Assembly of the Union of the Comoros","COD":"National Assembly (Democratic Republic of the Congo)","COG":"National Assembly (Republic of the Congo)","CRI":"Legislative Assembly of Costa Rica","CIV":"National Assembly (Ivory Coast)","HRV":"Croatian Parliament","CUB":"National Assembly of People's Power","CYP":"House of Representatives (Cyprus)","CZE":"Chamber of Deputies of the Czech Republic","DNK":"Folketing","DJI":"National Assembly (Djibouti)","DMA":"House of Assembly of Dominica","DOM":"Chamber of Deputies of the Dominican Republic","ECU":"National Assembly (Ecuador)","EGY":"House of Representatives (Egypt)","SLV":"Legislative Assembly of El Salvador","GNQ":"Chamber of Deputies (Equatorial Guinea)","ERI":"National Assembly (Eritrea)","EST":"Riigikogu","SWZ":"House of Assembly of Eswatini","ETH":"House of Peoples' Representatives","FJI":"Parliament of Fiji","FIN":"Parliament of Finland","FRA":"National Assembly (France)","GBR":"House of Commons of the United Kingdom","DZA":"People's National Assembly"}
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
    out[iso] = {"title": t, "len": len(w), "infobox": ib[:6000], "lines": keep[:80]}
    time.sleep(0.5)
json.dump(out, open("parliaments_raw.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: (v.get("error") or len(v["infobox"])) for k, v in out.items()})
