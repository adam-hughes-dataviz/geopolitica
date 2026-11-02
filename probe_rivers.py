"""Probe: can Wikidata give the longest river (and a lake) for the countries that have none, and can OpenStreetMap supply the line to draw?
Prints a report only. Writes nothing to the repo."""
import json, re, time, urllib.request, urllib.parse

RIVER = ["DZA", "AND", "ATG", "BHS", "BHR", "BRB", "BLZ", "CPV", "COM", "CUB", "CYP", "DNK", "DJI", "DMA", "SWZ", "FJI"]
LAKE = ["AND", "BHR", "BRB", "COM", "DMA", "GNQ"]
UA = {"User-Agent": "geopolitica-dashboard-probe/1.0 (https://github.com/adam-hughes-dataviz/geopolitica)"}

def http(url, accept="application/json", tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=dict(UA, Accept=accept))
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            try: b = e.read()[:150].decode("utf-8", "replace")
            except Exception: b = ""
            print("  HTTP", e.code, url[:100], "|", b)
            if e.code in (400, 404): return None
            time.sleep(8)
        except Exception as e:
            print("  ERR", type(e).__name__, str(e)[:80]); time.sleep(5)
    return None

def sparql(q):
    t = http("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q))
    try: return json.loads(t)["results"]["bindings"]
    except Exception: return None

print("=== A. Rivers (Wikidata): longest few per country, with how many countries each river is in ===")
firstosm = {}
for iso in RIVER:
    q = '''SELECT ?r ?rl ?len ?osm (COUNT(DISTINCT ?c2) AS ?n) WHERE {
      ?cx wdt:P298 "%s". ?r wdt:P31 wd:Q4022; wdt:P17 ?cx; wdt:P2043 ?len; wdt:P17 ?c2.
      OPTIONAL{?r wdt:P402 ?osm} ?r rdfs:label ?rl FILTER(LANG(?rl)="en")
    } GROUP BY ?r ?rl ?len ?osm ORDER BY DESC(xsd:decimal(?len)) LIMIT 6''' % iso
    rows = sparql(q)
    time.sleep(3)
    if rows is None:
        print(iso, "query failed"); continue
    print(iso, "| rivers found:", len(rows))
    for r in rows:
        own = int(r["n"]["value"]) == 1
        print("   %-28s %7s km | countries: %s | osm relation: %s" % (r["rl"]["value"][:28], r["len"]["value"][:7], r["n"]["value"], r.get("osm", {}).get("value", "-")))
        if own and r.get("osm") and iso not in firstosm:
            firstosm[iso] = (r["rl"]["value"], r["osm"]["value"])

print("\n=== B. Lakes (Wikidata) ===")
for iso in LAKE:
    q = '''SELECT ?l ?ll ?area ?osm WHERE {
      ?cx wdt:P298 "%s". ?l wdt:P31/wdt:P279* wd:Q23397; wdt:P17 ?cx. OPTIONAL{?l wdt:P2046 ?area} OPTIONAL{?l wdt:P402 ?osm}
      ?l rdfs:label ?ll FILTER(LANG(?ll)="en")
    } ORDER BY DESC(xsd:decimal(?area)) LIMIT 4''' % iso
    rows = sparql(q)
    time.sleep(3)
    print(iso, "|", "query failed" if rows is None else [(r["ll"]["value"], r.get("area", {}).get("value", "-"), r.get("osm", {}).get("value", "-")) for r in rows])

print("\n=== C. Can OpenStreetMap give the line for the longest contained river? ===")
for iso, (name, rel) in firstosm.items():
    t = http("https://api.openstreetmap.org/api/0.6/relation/%s/full.json" % rel)
    time.sleep(2)
    try:
        els = json.loads(t)["elements"]
        nodes = [e for e in els if e["type"] == "node"]
        print(iso, name, "relation", rel, "| nodes:", len(nodes), "| ways:", sum(1 for e in els if e["type"] == "way"))
    except Exception:
        print(iso, name, "relation", rel, "| could not read geometry")
print("\nprobe finished")
