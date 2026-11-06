import json, re, html
TT = {}
d = json.load(open('country-data.json')); P = json.load(open('parliaments.json')); PC = json.load(open('party_colours.json')); CT = json.load(open('colour_titles.json'))
def colour(t):
    c = html.unescape(PC.get(t) or "")
    return None if c.upper() in ("#F8F9FA", "#DCDCDC", "") else c
FALL = {"Social Liberal Party (Denmark)": "#733280"}   # Wikipedia's party colour is unset; the party's own purple
# 1. recolour the hand-kept tables
for iso, mp in CT.items():
    if iso == "EST": continue
    for x in d[iso]['tabs']['government']:
        if x.get('t') == 'table' and 'eat' in x['head'][1]:
            for r in x['rows']:
                t = mp.get(r[0])
                if t: TT[(iso, r[0])] = t
                if t:
                    c = colour(t) or FALL.get(t)
                    while len(r) < 3: r.append("")
                    if len(r) == 3: r.append(c or "")
                    else: r[3] = c or ""
# 2. new tables from Wikipedia
INCL = "ALB AND AGO ATG ARG AUS AZE BLR BLZ BEN BTN BOL BGR BRB CPV KHM CMR CAN TCD CHL COL COM COG CRI CIV HRV CYP CZE DOM ECU SLV GNQ FJI FIN FRA".split()
TITLE = {"ALB": "Assembly", "AND": "General Council", "AGO": "National Assembly", "ATG": "House of Representatives", "ARG": "Chamber of Deputies", "AUS": "House of Representatives", "AZE": "National Assembly", "BLR": "House of Representatives", "BLZ": "House of Representatives", "BEN": "National Assembly", "BTN": "National Assembly", "BOL": "Chamber of Deputies", "BGR": "National Assembly", "BRB": "House of Assembly", "CPV": "National Assembly", "KHM": "National Assembly", "CMR": "National Assembly", "CAN": "House of Commons", "TCD": "National Assembly", "CHL": "Chamber of Deputies", "COL": "Chamber of Representatives", "COM": "Assembly of the Union", "COG": "National Assembly", "CRI": "Legislative Assembly", "CIV": "National Assembly", "HRV": "Sabor", "CYP": "House of Representatives", "CZE": "Chamber of Deputies", "DOM": "Chamber of Deputies", "ECU": "National Assembly", "SLV": "Legislative Assembly", "GNQ": "Chamber of Deputies", "FJI": "Parliament", "FIN": "Eduskunta", "FRA": "National Assembly"}
def clean(n): return re.sub(r"\s+", " ", n).strip()
GREYN = re.compile(r"^(independent|non-attached|vacan|others?|speaker|unaffiliated)", re.I)
for iso in INCL:
    v = P[iso]; rows = []
    for r in v['rows']:
        c = None if GREYN.match(r['n']) else (colour_c := (r['c'] if r['c'] and r['c'].upper() not in ('#DCDCDC', '#F8F9FA', '#DDDDDD', '#FFFFFF') else None))
        if r['a']: TT[(iso, clean(r['n']))] = r['a']
        row = [clean(r['n']), str(r['s']), "In government" if v['gov_total'] and r['gov'] and not all(x['gov'] for x in v['rows']) else "", c or ""]
        rows.append(row)
    tab = [{"t": "h", "v": TITLE[iso] + " (current seats)"}, {"t": "table", "head": ["Party", "Seats"], "rows": rows}]
    g = d[iso]['tabs']['government']
    g[:] = [x for x in g if not (x.get('t') == 'table' and 'eat' in x['head'][1]) and not (x.get('t') == 'h' and re.search(r'eduskunta|folketing|\(\d{4}|current seats', x.get('v', ''), re.I))]
    i = next((k for k, x in enumerate(g) if x.get('t') == 'live'), len(g)); g[i:i] = tab
# Estonia: 2023 election result
for _n, _s, _t in [("Reform Party", 37, "Estonian Reform Party"), ("Conservative People's Party", 17, "Conservative People's Party of Estonia"), ("Centre Party", 16, "Estonian Centre Party"), ("Estonia 200", 14, "Estonia 200"), ("Social Democrats", 9, "Social Democratic Party (Estonia)"), ("Isamaa", 8, "Isamaa")]: TT[('EST', _n)] = _t
EST = [("Reform Party", 37, "Estonian Reform Party"), ("Conservative People's Party", 17, "Conservative People's Party of Estonia"), ("Centre Party", 16, "Estonian Centre Party"), ("Estonia 200", 14, "Estonia 200"), ("Social Democrats", 9, "Social Democratic Party (Estonia)"), ("Isamaa", 8, "Isamaa")]
g = d['EST']['tabs']['government']; i = next((k for k, x in enumerate(g) if x.get('t') == 'live'), len(g))
g[i:i] = [{"t": "h", "v": "Riigikogu (2023 election result)"}, {"t": "table", "head": ["Party", "Seats"], "rows": [[n, str(s), "", colour(t) or ""] for n, s, t in EST]}]
# 3. opposition leader
FORMAL = {}
for iso, v in P.items():
    for o in v.get('opp_office') or []:
        m = re.match(r"(?:Leader of (?:the )?Opposition|Opposition Leader):\s*(.+?)\s*,\s*([^,]+?)\s+since", o)
        if m and not o.startswith("Deputy"): FORMAL[iso] = f"{clean(m.group(1))} ({clean(m.group(2))})"
PARL = "ALB AND AUS BHS BEL BLZ BTN BWA BGR CPV CAN HRV CZE DNK FJI FIN FRA GBR BGD EST AUT COM BRB".split()
LARGEST = {}
for iso in PARL:
    v = P.get(iso) or {}
    ol = v.get('opp_party_leader')
    if ol and ol[1]: LARGEST[iso] = f"{clean(ol[1])} ({clean(ol[0])}), leader of the largest opposition party"
LARGEST["AUT"] = "Herbert Kickl (FPÖ), leader of the largest opposition party"
LARGEST["EST"] = "Martin Helme (EKRE), leader of the largest opposition party"
LARGEST["FRA"] = "Marine Le Pen (RN), president of the largest opposition group"
FORMAL["BRB"] = "None at present. The governing BLP holds all 30 seats"
FORMAL["CAN"] = "Pierre Poilievre (Conservative Party of Canada)"
FORMAL["COM"] = "Mohamed Omar Abubakar"
FORMAL["ATG"] = "Jamale Pringle (UPP)"
FORMAL["DMA"] = "Jesma Paul-Victor (Independent)"

# ---- hand-checked extras (infobox layout defeats the parser)
def setchart(iso, head, rows):
    g = d[iso]['tabs']['government']
    g[:] = [x for x in g if not (x.get('t') == 'table' and len(x['head']) > 1 and 'eat' in x['head'][1])]
    i = next((k for k, x in enumerate(g) if x.get('t') == 'live'), len(g)); g[i:i] = [{"t": "h", "v": head}, {"t": "table", "head": ["Party", "Seats"], "rows": rows}]
def fromP(iso, upto=None, govn=0):
    rr = P[iso]['rows'][:upto]; out = []
    for k, r in enumerate(rr):
        c = None if GREYN.match(r['n']) or (r['c'] or '').upper() in ('#DCDCDC', '#F8F9FA', '#DDDDDD', '#FFFFFF', '#00000000') else r['c']
        if r['a']: TT[(iso, clean(r['n']).replace('︙ ', ''))] = r['a']
        out.append([clean(r['n']).replace('︙ ', ''), str(r['s']), "In government" if k < govn else "", c or ""])
    return out
setchart("BHR", "Council of Representatives (2022 election)", [["Independents", "38", "", "#8a97a0"], ["National Unity Assembly", "1", "", "#4e79a7"], ["Al-Rabita Islamic Society", "1", "", "#59a14f"]])

setchart('ARM', "National Assembly (current seats)", [["Civil Contract", "64", "In government", "#5169B1"], ["Strong Armenia", "29", "", "#001489"], ["Armenia Alliance", "12", "", "#1D2E69"]])
setchart('BHS', "House of Assembly (current seats)", [["Progressive Liberal Party", "33", "In government", "#FFD700"], ["Free National Movement", "8", "", "#e30513"]])
setchart('DJI', "National Assembly (current seats)", [["Union for the Presidential Majority", "58", "In government", "#5FB989"], ["Djibouti Union for Democracy and Justice", "7", "", "#000000"]])
setchart('DMA', "House of Assembly (current seats)", [["Dominica Labour Party", "19", "In government", "#BE1E2D"], ["Government senators", "5", "In government", "#BE1E2D"], ["Opposition senators", "4", "", "#2E3092"], ["Independent", "2", "", ""], ["Attorney General and Speaker (ex officio)", "2", "", ""]])
setchart('BRA', "Chamber of Deputies (outgoing legislature)", fromP('BRA', 15, 6))
setchart('COD', "National Assembly (current seats)", fromP('COD'))
setchart('BDI', "National Assembly (current seats)", [["CNDD-FDD", "108", "In government", "#CC0001"], ["Twa", "3", "", ""]])
er = fromP('EGY'); er += [["Independents, appointed and vacant", "109", "", ""]]
for r in er[:10]: r[2] = "In government"
setchart('EGY', "House of Representatives (current seats)", er)
setchart('ETH', "House of Peoples' Representatives (2026 results declared)", [["Prosperity Party", "438", "In government", "#FFCD29"], ["EZEMA", "13", "", ""], ["National Movement of Amhara", "6", "", "#B97433"], ["Medrek", "3", "", ""], ["Freedom and Equality Party", "3", "", ""], ["Coalition for Unity and Democracy", "2", "", ""], ["Independents", "8", "", ""]])
FORMAL["ARM"] = "Samvel Karapetyan (Strong Armenia), leader of the largest opposition party. He is in pre-trial detention"

MT = {('ARM','Civil Contract'):'Civil Contract (Armenia)',('ARM','Strong Armenia'):'Strong Armenia',('ARM','Armenia Alliance'):'Armenia Alliance',('BHS','Progressive Liberal Party'):'Progressive Liberal Party (Bahamas)',('BHS','Free National Movement'):'Free National Movement',('DJI','Union for the Presidential Majority'):'Union for the Presidential Majority',('DJI','Djibouti Union for Democracy and Justice'):'Djibouti Union for Democracy and Justice',('DMA','Dominica Labour Party'):'Dominica Labour Party',('BDI','CNDD-FDD'):'National Council for the Defense of Democracy – Forces for the Defense of Democracy',('ETH','Prosperity Party'):'Prosperity Party',('ETH','EZEMA'):'Ethiopian Citizens for Social Justice',('ETH','National Movement of Amhara'):'National Movement of Amhara',('ETH','Medrek'):'Medrek',('ETH','Freedom and Equality Party'):'Freedom and Equality Party (Ethiopia)',('ETH','Coalition for Unity and Democracy'):'Coalition for Unity and Democracy'}
TT.update(MT)
json.dump(sorted(set(TT.values())), open('leader_titles.json', 'w'), ensure_ascii=False, indent=1)
import os
LD = json.load(open('leaders.json')) if os.path.exists('leaders.json') else {}
LD.update({'Bangladesh Jamaat-e-Islami': 'Shafiqur Rahman', 'National Citizen Party': 'Nahid Islam'})
TT[('BGD','National Citizen Party')] = 'National Citizen Party'
SKIP = re.compile(r"^(vacant|none|n/a)$", re.I)
for iso, v in d.items():
    for x in v['tabs'].get('government', []):
        if x.get('t') == 'table' and len(x['head']) > 1 and 'eat' in x['head'][1] and len(x['head']) < 3:
            for r in x['rows']:
                ld = LD.get(TT.get((iso, r[0])) or '')
                gv = r[2] if len(r) > 2 else ''
                if ld and not SKIP.match(ld): note = ld + (" · govt" if gv else "")
                else: note = gv
                while len(r) < 4: r.append("")
                r[2] = note
                if iso == 'FRA' and r[0] == 'NI': r[0] = 'Non-attached members'
                tt = TT.get((iso, r[0]))
                if tt and not GREYN.match(r[0]) and not re.match(r"(es|fr|de):|list of", tt, re.I) and "page does not exist" not in tt:
                    nm = re.sub(r"\s*\([^)]*\)", "", tt).strip(); nm = re.sub(r"\s+group$", "", nm, flags=re.I).strip()
                    nm = {"UDR": "Union of the Right for the Republic"}.get(nm, nm)
                    if nm and not GREYN.match(nm): r[0] = nm
OUT = {}
for iso, v in d.items():
    rows = next((x for x in v['tabs'].get('government', []) if x.get('t') == 'rows'), None)
    if not rows: continue
    for r in rows['rows']:
        if r[0] == 'Opposition leader':
            val = FORMAL.get(iso) or (LARGEST.get(iso) if iso in PARL else None)
            if val: r[1] = val; OUT[iso] = val
            elif r[1] in ('n/a', ''): r[1] = "No formal opposition leader"; OUT[iso] = r[1]

ROWFULL = {"SNP":"Scottish National Party","DUP":"Democratic Unionist Party","MPLA":"People's Movement for the Liberation of Angola",
"UNITA":"National Union for the Total Independence of Angola","SER Santa Cruz":"Santa Cruz We Are Experience Renewal",
"BAP":"New Azerbaijan Party","APB Súmate":"Alliance of Bolivian Patriots Súmate","GERB–SDS":"Citizens for European Development of Bulgaria – Union of Democratic Forces",
"FUNCINPEC":"National United Front for an Independent, Neutral, Peaceful and Cooperative Cambodia","UDI":"Independent Democratic Union",
"MIRA":"Independent Movement of Absolute Renovation","MAIS":"Alternative Indigenous and Social Movement","PARI":"Party for the Recovery of the Comoros",
"AFDC-A":"Alliance of Democratic Forces of the Congo and Allies","AAAP":"Alliance of Allies for the Alternation Pact","2A/TDC":"Alliance for Change and Democratic Transition",
"4AC":"Alliance of Four for Change","AACPG":"Alliance of Allies for the Congolese People","ANB":"New Bloc Alliance","AA/C":"Alliance of Allies and Cadres",
"MUST":"Union for Democratic Movements","SDSS":"Independent Democratic Serb Party","ELAM":"National Popular Front","ELAM":"National Popular Front",
"ALMA – Citizens for Cyprus":"Alma – Citizens for Cyprus","ANO 2011":"Action of Dissatisfied Citizens","KDU-ČSL":"Christian and Democratic Union – Czechoslovak People's Party",
"TOP 09":"Tradition, Responsibility, Prosperity 09","RETO Movement":"Ecuadorian Renewal Movement (RETO)","PSOL REDE Federation":"Socialism and Liberty Party – Sustainability Network Federation"}
OPPFULL = {"UPP":"United Progressive Party","FPÖ":"Freedom Party of Austria","FNM":"Free National Movement","Jamaat":"Jamaat-e-Islami","VB":"Vlaams Belang",
"UDP":"United Democratic Party","BTP":"Bhutan Tendrel Party","BCP":"Botswana Congress Party","PL":"Liberal Party","GERB–SDS":"Citizens for European Development of Bulgaria",
"MpD":"Movement for Democracy","URCA":"Union for a Central African Renaissance","SDP":"Social Democratic Party of Croatia","ODS":"Civic Democratic Party",
"Venstre":"Venstre, Liberal Party","EKRE":"Conservative People's Party of Estonia","RN":"National Rally","Democratic":"Democratic Party of Albania",
"Liberal":"Liberal Party of Australia"}
for iso, v in d.items():
    for x in v['tabs'].get('government', []):
        if x.get('t') == 'table' and len(x['head']) > 1 and 'eat' in x['head'][1]:
            for r in x['rows']:
                if iso != 'COL' or r[0] in ROWFULL: r[0] = ROWFULL.get(r[0], r[0])
        if x.get('t') == 'rows':
            for r in x['rows']:
                if r[0] == 'Opposition leader':
                    r[1] = re.sub(r"\(([^)]*)\)", lambda m: "(" + OPPFULL.get(m.group(1), m.group(1)) + ")", r[1], count=1)

FILL = {
("AFG","Ruling party or coalition"):"Taliban (Islamic Emirate of Afghanistan). Political parties are banned",
("DZA","Ruling party or coalition"):"No governing party. President Tebboune is an independent backed by the National Liberation Front and allied parties",
("BHR","Ruling party or coalition"):"None. Political parties are prohibited and the Al Khalifa monarchy governs",
("BLR","Ruling party or coalition"):"None. President Lukashenko governs without a party",
("BEN","Ruling party or coalition"):"Republican Bloc and Progressive Union for Renewal coalition",
("BIH","Ruling party or coalition"):"Multi-party coalition, with no single ruling party",
("BRN","Ruling party or coalition"):"None. The Sultan governs as an absolute monarch and parties play no role",
("BFA","Ruling party or coalition"):"None. Military government led by Captain Ibrahim Traoré",
("CHN","Ruling party or coalition"):"Chinese Communist Party",
("COL","Ruling party or coalition"):"Defenders of the Homeland, in coalition with the Democratic Center, Conservative Party, Radical Change and We Believe",
("CRI","Ruling party or coalition"):"Sovereign People's Party, which holds 31 of the 57 seats",
("CUB","Ruling party or coalition"):"Communist Party of Cuba",
("BIH","Next election"):"General election expected in October 2030",
("BRN","Next election"):"None scheduled",
("BFA","Next election"):"None scheduled",
("CHN","Next election"):"No competitive national elections. The next National People's Congress is due in March 2028",
("GBR","Last election"):"General election: 4 July 2024. Labour won 411 of the 650 seats",
("BHR","Last election"):"Legislative: November 2022",
("HRV","Last election"):"Legislative: 17 April 2024. Presidential: 29 December 2024, with a runoff on 12 January 2025",
("BEN","Emergency number"):"117 (police), 112 (ambulance), 118 (fire)",
("BDI","Emergency number"):"117 (police), 112 (ambulance), 118 (fire)",
("CMR","Emergency number"):"112 (also 117 police, 119 ambulance, 118 fire)",
("CAF","Emergency number"):"117 (police), 1220 (ambulance), 118 (fire)",
("TCD","Emergency number"):"17 (police), 2251-4242 (ambulance), 18 (fire)",
("COM","Emergency number"):"17 (police), 772-03-73 (ambulance), 18 (fire)",
("COD","Emergency number"):"112 (police), 118 (fire)",
("COG","Emergency number"):"117 (police), 118 (fire)",
("CIV","Emergency number"):"110, 111 or 170 (police), 185 (ambulance), 180 (fire)",
("DJI","Emergency number"):"17 (police), 19 (ambulance), 18 (fire)",
("GNQ","Emergency number"):"114 (police), 115 (ambulance), 112 (fire)",
("ERI","Emergency number"):"113 (police), 114 (ambulance), 116 (fire)",
("CYP","Ruling party or coalition"):"None. President Nikos Christodoulides is an independent in a presidential system",
("EGY","Ruling party or coalition"):"Nation's Future Party, the largest party in parliament, backs President Sisi",
("ERI","Ruling party or coalition"):"People's Front for Democracy and Justice, the only legal party",
("ETH","Emergency number"):"991 (police), 907 (ambulance), 939 (fire)",
("SWZ","Ruling party or coalition"):"None. Parties cannot contest elections and King Mswati III appoints the government",
}
for iso, v in d.items():
    for t, xs in v['tabs'].items():
        for x in xs:
            for r in x.get('rows', []):
                if len(r) > 1 and str(r[1]).strip().lower() == 'n/a' and (iso, r[0]) in FILL: r[1] = FILL[(iso, r[0])]

for x in d['DZA']['tabs']['government']:
    if x.get('t') == 'table' and len(x['head']) > 1 and 'eat' in x['head'][1]:
        for r in x['rows']:
            if r[0] == 'National Democratic Rally': r[0] = 'Democratic National Rally'; r[2] = 'Monder Bouden'
            if r[0] == 'El Bina': r[0] = 'National Construction Movement (El Bina)'; r[2] = 'Abdelkader Bengrina'
json.dump(d, open('country-data.json', 'w'), ensure_ascii=False)
for k, x in sorted(OUT.items()): print(k, '|', x)
