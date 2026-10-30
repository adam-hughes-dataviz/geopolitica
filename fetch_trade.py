"""Collect top-5 goods trade (UN Comtrade public preview API) into trade.json.
Runs daily on GitHub Actions. Each run fills missing countries first, then the oldest entries,
up to MAX_COUNTRIES per run, so rate limits never stop the whole job."""
import json, os, re, sys, time, urllib.request, datetime

MAX_COUNTRIES = int(os.environ.get("MAX_COUNTRIES", "40"))
FRESH_DAYS = 28
OVERRIDE = {"FRA": "251", "ITA": "381", "NOR": "579", "CHE": "757", "USA": "842", "IND": "699", "TWN": "490"}
API = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"

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
            req = urllib.request.Request(url, headers={"User-Agent": "geopolitica-dashboard"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r).get("data") or []
        except urllib.error.HTTPError as e:
            if e.code == 429:
                raise RuntimeError("rate limited")
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
            n = x.get("partnerDesc") or ""
            if re.search(r"\bnes\b|special categories|bunkers|free zones|^world$", n, re.I):
                continue
            lst.append([n, v])
        else:
            if code == "TOTAL":
                tot = max(tot, v); continue
            if code in ("99", "9999"):
                continue
            lst.append([short(x.get("cmdDesc")), v])
    lst.sort(key=lambda a: -a[1])
    return {"tot": tot or sum(a[1] for a in lst), "top": lst[:5]}

def country(code):
    now = datetime.date.today().year
    for y in (now - 2, now - 3, now - 4):
        base = "%s?reporterCode=%s&period=%d&partner2Code=0&customsCode=C00&motCode=0&maxRecords=500" % (API, code, y)
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
    todo = [k for k in codes() if not data.get(k) or now - data[k].get("t", 0) > FRESH_DAYS * 86400]
    todo.sort(key=lambda k: data.get(k, {}).get("t", 0))
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
