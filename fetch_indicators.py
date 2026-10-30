"""Collect key economy and population figures for every country into indicators.json.
IMF World Economic Outlook (DataMapper API) and World Bank open data. No keys needed."""
import json, time, urllib.request, urllib.error, datetime

NOW = datetime.date.today().year
IMF = {"NGDP_RPCH": "gdpg", "LUR": "unemp", "PCPIPCH": "infl", "NGDPD": "gdp", "NGDPDPC": "gdppc", "PPPGDP": "ppp", "PPPPC": "pppc",
       "GGXWDG_NGDP": "debt", "GGXCNL_NGDP": "bal", "BCA_NGDPD": "ca"}
WB = {"SP.POP.TOTL": "pop", "SP.URB.TOTL.IN.ZS": "urban", "SP.DYN.LE00.IN": "life", "SP.POP.GROW": "popg", "EN.POP.DNST": "dens", "SP.DYN.TFRT.IN": "fert", "SI.POV.GINI": "gini",
      "NY.GDP.MKTP.KD.ZG": "gdpg2", "SL.UEM.TOTL.ZS": "unemp2", "FP.CPI.TOTL.ZG": "infl2", "GC.DOD.TOTL.GD.ZS": "debt2", "GC.NLD.TOTL.GD.ZS": "bal2", "BN.CAB.XOKA.GD.ZS": "ca2",
      "NY.GDP.MKTP.CD": "gdp2", "NY.GDP.PCAP.CD": "gdppc2", "NY.GDP.MKTP.PP.CD": "ppp2", "NY.GDP.PCAP.PP.CD": "pppc2",
      "GOV_WGI_VA_SC": "voice", "GOV_WGI_PV_SC": "stab", "GOV_WGI_GE_SC": "eff", "GOV_WGI_RL_SC": "law", "GOV_WGI_CC_SC": "corr"}

def get(url):
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36", "Accept": "application/json, text/plain, */*", "Accept-Language": "en-GB,en;q=0.9", "Referer": "https://www.imf.org/external/datamapper/"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            print("blocked" if e.code in (401, 403) else "retry", url[:80], e)
            if e.code in (401, 403, 404): return None
            time.sleep(4)
        except Exception as e:
            print("retry", url[:80], e); time.sleep(4)
    return None

def main():
    out = {}
    for code, key in IMF.items():
        j = get("https://www.imf.org/external/datamapper/api/v1/" + code)
        vals = ((j or {}).get("values") or {}).get(code) or {}
        n = 0
        for iso, series in vals.items():
            ys = sorted(int(y) for y, v in series.items() if v is not None and int(y) <= NOW)
            if ys:
                out.setdefault(iso, {})[key] = [series[str(ys[-1])], ys[-1]]; n += 1
        print("imf", code, n); time.sleep(1)
    for code, key in WB.items():
        gov = code.startswith("GOV_WGI")
        tries = ["https://api.worldbank.org/v2/country/all/indicator/%s?format=json&mrnev=1&per_page=500" % code]
        if gov:
            tries = ["https://api.worldbank.org/v2/country/all/indicator/%s?format=json&mrnev=1&per_page=500" % code,
                     "https://api.worldbank.org/v2/country/all/indicator/%s?format=json&date=2020:2026&per_page=3000" % code]
        n = 0
        for url in tries:
            j = get(url)
            rows = (j[1] if isinstance(j, list) and len(j) > 1 else None) or []
            best = {}
            for r in rows:
                iso = r.get("countryiso3code")
                if iso and r.get("value") is not None:
                    y = int(r["date"])
                    if iso not in best or y > best[iso][1]: best[iso] = [r["value"], y]
            for iso, v in best.items(): out.setdefault(iso, {})[key] = v
            n = len(best)
            if n: break
        print("wb", code, n); time.sleep(1)
    if len(out) < 100:
        raise SystemExit("too few countries (%d), not publishing" % len(out))
    json.dump(out, open("indicators.json", "w"), separators=(",", ":"))
    print("countries:", len(out))

main()
