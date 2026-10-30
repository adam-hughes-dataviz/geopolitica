"""Collect top-5 goods trade (UN Comtrade public preview API) into trade.json.
Runs daily on GitHub Actions. Each run fills missing countries first, then the oldest entries,
up to MAX_COUNTRIES per run (set high so every country is collected), so rate limits never stop the whole job."""
import json, os, re, sys, time, urllib.request, datetime

MAX_COUNTRIES = int(os.environ.get("MAX_COUNTRIES", "400"))
FRESH_DAYS = 28
OVERRIDE = {"FRA": "251", "ITA": "381", "NOR": "579", "CHE": "757", "USA": "842", "IND": "699", "TWN": "490"}
KEY = os.environ.get("COMTRADE_KEY", "").strip()
API = "https://comtradeapi.un.org/data/v1/get/C/A/HS" if KEY else "https://comtradeapi.un.org/public/v1/preview/C/A/HS"

CH = {"01":"Live animals","02":"Meat","03":"Fish and seafood","04":"Dairy, eggs and honey","05":"Other animal products","06":"Live plants and flowers","07":"Vegetables","08":"Fruit and nuts","09":"Coffee, tea and spices","10":"Cereals","11":"Milling products","12":"Oil seeds and grains","13":"Gums and resins","14":"Vegetable plaiting materials","15":"Fats and oils","16":"Prepared meat and fish","17":"Sugar","18":"Cocoa and chocolate","19":"Baked goods and pasta","20":"Prepared vegetables and fruit","21":"Miscellaneous food","22":"Beverages and spirits","23":"Animal feed and food waste","24":"Tobacco","25":"Salt, stone and cement","26":"Ores","27":"Mineral fuels and oil","28":"Inorganic chemicals","29":"Organic chemicals","30":"Pharmaceuticals","31":"Fertilisers","32":"Dyes and paints","33":"Perfumes and cosmetics","34":"Soap and waxes","35":"Glues and starches","36":"Explosives and matches","37":"Photographic goods","38":"Miscellaneous chemicals","39":"Plastics","40":"Rubber","41":"Raw hides and skins","42":"Leather goods and bags","43":"Furs","44":"Wood","45":"Cork","46":"Basketware","47":"Wood pulp","48":"Paper and paperboard","49":"Books and printed matter","50":"Silk","51":"Wool","52":"Cotton","53":"Other vegetable fibres","54":"Man-made filaments","55":"Man-made staple fibres","56":"Wadding and felt","57":"Carpets","58":"Special woven fabrics","59":"Coated textiles","60":"Knitted fabrics","61":"Knitted clothing","62":"Woven clothing","63":"Other textile articles","64":"Footwear","65":"Headgear","66":"Umbrellas","67":"Feathers and artificial flowers","68":"Stone and plaster articles","69":"Ceramics","70":"Glass","71":"Precious metals and gems","72":"Iron and steel","73":"Iron and steel articles","74":"Copper","75":"Nickel","76":"Aluminium","78":"Lead","79":"Zinc","80":"Tin","81":"Other base metals","82":"Tools and cutlery","83":"Miscellaneous metal goods","84":"Machinery and boilers","85":"Electrical equipment","86":"Railway vehicles","87":"Cars and vehicles","88":"Aircraft and spacecraft","89":"Ships and boats","90":"Optical and medical instruments","91":"Clocks and watches","92":"Musical instruments","93":"Arms and ammunition","94":"Furniture and bedding","95":"Toys and games","96":"Miscellaneous manufactures","97":"Works of art and antiques"}
PNAME = {"251": "France", "381": "Italy", "579": "Norway", "757": "Switzerland", "842": "United States", "699": "India", "490": "Taiwan", "97": "European Union", "568": "Other Europe", "699": "India"}

def pname(code, desc):
    if desc and str(desc).strip():
        return str(desc).strip()
    c = str(int(code)) if str(code).isdigit() else str(code)
    if c in PNAME:
        return PNAME[c]
    try:
        import pycountry
        p = pycountry.countries.get(numeric=c.zfill(3))
        if p:
            return getattr(p, "common_name", None) or p.name
    except Exception:
        pass
    return ""

def bad(d):
    return not d or not d.get("px") or any((not a[0]) for k in ("px", "pm", "cx", "cm") for a in d[k]["top"])

def codes():
    keys = []
    for line in open("codes.txt", encoding="utf-8"):
        k = line.split(" ", 1)[0].strip()
        if re.fullmatch(r"[A-Z]{3}", k) and k not in keys:
            keys.append(k)
    return keys

def numeric(k):
    if k in OVERRIDE:
        return OVERRIDE[k]
    import pycountry
    c = pycountry.countries.get(alpha_3=k)
    return str(int(c.numeric)) if c else None

def get(url):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=dict({"User-Agent": "geopolitica-dashboard"}, **({"Ocp-Apim-Subscription-Key": KEY} if KEY else {})))
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r).get("data") or []
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise RuntimeError("access refused (HTTP %d), check the COMTRADE_KEY secret" % e.code)
            if e.code == 429:
                raise RuntimeError("rate limited" + ("" if KEY else " (no COMTRADE_KEY set)"))
            if e.code in (400, 404):
                return []
            time.sleep(3)
        except Exception:
            time.sleep(3)
    return []

def short(t):
    return re.sub(r"\s+", " ", re.split(r"[;,]", str(t or ""))[0]).strip()

def pick(rows, partners):
    tot, lst = 0, []
    for x in rows:
        v = x.get("primaryValue") or x.get("fobvalue") or x.get("cifvalue") or 0
        if not v or v <= 0:
            continue
        code, pc = str(x.get("cmdCode")), str(x.get("partnerCode"))
        if partners:
            if pc == "0":
                tot = max(tot, v); continue
            n = pname(pc, x.get("partnerDesc"))
            if not n:
                continue
            if re.search(r"\bnes\b|special categories|bunkers|free zones|^world$", n, re.I):
                continue
            lst.append([n, v])
        else:
            if code == "TOTAL":
                tot = max(tot, v); continue
            if code in ("99", "9999"):
                continue
            lst.append([CH.get(code.zfill(2)) or short(x.get("cmdDesc")), v])
    lst.sort(key=lambda a: -a[1])
    return {"tot": tot or sum(a[1] for a in lst), "top": lst[:5]}

def country(code):
    now = datetime.date.today().year
    for y in (now - 2, now - 3, now - 4):
        base = "%s?reporterCode=%s&period=%d&partner2Code=0&customsCode=C00&motCode=0&maxRecords=500&includeDesc=true" % (API, code, y)
        px = get(base + "&cmdCode=AG2&flowCode=X&partnerCode=0"); time.sleep(1.2)
        pm = get(base + "&cmdCode=AG2&flowCode=M&partnerCode=0"); time.sleep(1.2)
        cx = get(base + "&cmdCode=TOTAL&flowCode=X"); time.sleep(1.2)
        cm = get(base + "&cmdCode=TOTAL&flowCode=M"); time.sleep(1.2)
        out = {"y": y, "px": pick(px, False), "pm": pick(pm, False), "cx": pick(cx, True), "cm": pick(cm, True)}
        if any(out[k]["top"] for k in ("px", "pm", "cx", "cm")):
            out["t"] = int(time.time())
            return out
    return None

def main():
    try:
        data = json.load(open("trade.json", encoding="utf-8"))
    except Exception:
        data = {}
    now = time.time()
    todo = [k for k in codes() if bad(data.get(k)) and not (data.get(k) or {}).get("none") or now - data[k].get("t", 0) > FRESH_DAYS * 86400]
    todo.sort(key=lambda k: 0 if bad(data.get(k)) else data[k].get("t", 0))
    done = 0
    for k in todo:
        if done >= MAX_COUNTRIES:
            break
        n = numeric(k)
        if not n:
            continue
        try:
            r = country(n)
        except RuntimeError as e:
            print("stopping:", e); break
        done += 1
        if r:
            data[k] = r; print("ok", k, r["y"])
        else:
            data[k] = {"t": int(time.time()), "none": True}; print("none", k)
    json.dump(data, open("trade.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("countries done this run:", done, "total:", len(data))

if __name__ == "__main__":
    main()
