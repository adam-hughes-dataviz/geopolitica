"""Current party leaders from each party's Wikipedia infobox -> leaders.json {article title: leader name}."""
import json, re, time, urllib.request, urllib.parse
from bs4 import BeautifulSoup
UA = {"User-Agent": "geopolitica-dashboard/1.0 (https://github.com/adam-hughes-dataviz/geopolitica)"}
TITLES = json.load(open("leader_titles.json", encoding="utf-8"))
ROW = re.compile(r"^(party )?(leader|co-?leader|chair(man|woman|person)?|president|general secretary|secretary[- ]general|first secretary|leader of the party)s?\b", re.I)
out = {}
for t in TITLES:
    u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "parse", "page": t, "prop": "text", "format": "json", "redirects": 1, "formatversion": 2})
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r: h = json.load(r)["parse"]["text"]
    except Exception: out[t] = None; continue
    ib = BeautifulSoup(h, "html.parser").find("table", class_=re.compile("infobox")); name = None
    if ib:
        for tr in ib.find_all("tr"):
            th, td = tr.find("th"), tr.find("td")
            if th and td and ROW.match(th.get_text(" ", strip=True)):
                for a in td.find_all("a"):
                    x = a.get_text(" ", strip=True)
                    if x and not x.startswith("[") and not re.match(r"^\d", x) and "(" not in x and len(x) > 3: name = x; break
                if not name:
                    x = re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]|\([^)]*\)", "", td.get_text(" ", strip=True))).strip()
                    name = x or None
                break
    out[t] = name; time.sleep(0.4)
json.dump(out, open("leaders.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(sum(1 for v in out.values() if v), "of", len(out))
