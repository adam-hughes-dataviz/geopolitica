// Geopolitica news service. Runs free on Cloudflare Workers.
// GET /?c=Brazil&d=Chile  ->  same, for headlines mentioning both countries (up to five)
// GET /?c=Brazil  ->  { updated, items: [ {t, u, s, d}, x3 ] }  (three different recent stories)
// It reads Google News search results on the server, keeps the answer for 15 minutes, and allows the page to call it.

const QUERY = {
  "United Kingdom": '"United Kingdom" OR Britain',
  "United States of America": '"United States" OR "U.S."',
  "Georgia": "Georgia Tbilisi", "Jordan": "Jordan Amman", "Turkey": "Turkey OR Türkiye", "Niger": "Niger Niamey",
  "Chad": "Chad N'Djamena", "Guinea": "Guinea Conakry", "Ireland": "Ireland Dublin",
  "Palestine": 'Palestinian OR Gaza OR "West Bank"',
  "Democratic Republic of the Congo": '"DR Congo" OR "Democratic Republic of Congo"',
  "Republic of the Congo": '"Republic of Congo" OR Brazzaville',
  "The Bahamas": "Bahamas", "The Gambia": "Gambia", "Ivory Coast": '"Ivory Coast" OR "Côte d\'Ivoire"',
  "Czechia": "Czech", "Vatican City": "Vatican", "Sao Tome and Principe": '"Sao Tome"',
  "Cabo Verde": '"Cabo Verde" OR "Cape Verde"', "Côte d'Ivoire": '"Ivory Coast" OR "Côte d\'Ivoire"', "Timor-Leste": '"Timor-Leste" OR "East Timor"', "Micronesia": "Micronesia Pohnpei", "Samoa": "Samoa Apia"
};
const STOP = new Set("the a an and or of in on at to for with from by as is are was were be been it its this that after over into about amid says said say new will would could may more than not has have had who what when how why their his her they them".split(" "));
const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET", "Content-Type": "application/json; charset=utf-8" };

// Sports stories are left out: by source name, by address, and by title.
const SPORT_SRC = /sport|espn|cricket|cricbuzz|cricinfo|goal\.com|bleacher|athletic|onefootball|fox ?sports|yahoo sports|dazn|eurosport/i;
const SPORT_URL = /\/sports?(\/|-|\.)|sports\.|\/cricket|\/football|\/soccer|\/rugby|\/tennis|\/golf/i;
const SPORT_TTL = /\b(premier league|ecb|icc|bcci|pcb|super league|bundesliga|la liga|serie a|world cup qualif\w*|cricket|football|footballer|soccer|rugby|tennis|golf|golfer|pga|lpga|nba|nfl|nhl|mlb|fifa|uefa|concacaf|conmebol|ipl|t20|odi|wicket|wickets|batsman|bowler|goalkeeper|striker|olympic|olympics|paralympic|premier league|champions league|la liga|world cup|wwc|u-?17|u-?20|u-?21|asia cup|grand slam|formula (1|one)|f1|motogp|grand prix|athlete|athletes|medal|fixture|squash|hockey|kabaddi|wrestler|wrestling|boxer|boxing|ufc|mma|esports|surf|surfing|surfer|netball|basketball|baseball|volleyball|cycling|marathon|sprinter|championship|championships|round of 16|knockout|playoffs?|midfielder)\b/i;
const PAIR_OK = /\b(trade|trading|tariff|tariffs|sanction|sanctions|embargo|export|exports|import|imports|investment|invest|treaty|agreement|accord|deal|talks|negotiat\w*|summit|visit|visits|diplomat\w*|ambassador|embassy|consul\w*|foreign minister|foreign ministry|prime minister|president|minister|government|parliament|border|military|army|navy|troops|defen[cs]e|security|war|conflict|attack|strike|missile|drone|ceasefire|peace|alliance|nato|brics|asean|g20|g7|un|united nations|migration|migrants|refugees|visa|energy|oil|gas|climate|cooperation|partnership|relations|tensions|dispute|espionage|spy)\b/i;
// Syndication, social media, blogs, press-release wires and travel or lifestyle pieces are left out. They are not news reporting.
const BAD_SRC = /\bmsn\b|yahoo|tiktok|facebook|youtube|reddit|instagram|twitter|\bx\.com|medium\.com|^medium$|substack|pinterest|quora|linkedin|blogspot|wordpress|openpr|pr ?newswire|globenewswire|einpresswire|accesswire|benzinga|newsbreak|dailyhunt|flipboard|apple news|ground news|lonely planet|simple flying|\bblog\b/i;
const BAD_URL = /msn\.com|youtube\.|tiktok\.|facebook\.|reddit\.|instagram\.|twitter\.com|x\.com\/|medium\.com|substack\.|blogspot\.|wordpress\./i;
const BAD_TTL = /travel|tourist|tourism|vlog|influencer|honeymoon|recipe|horoscope|celebrity|fashion|lottery|jackpot|giveaway|\bTT\b|#\w+|how to |best places|things to do|bucket list|cancer|dating|obituary/i;
// Established outlets are ranked first. Anything not on this list is used only to fill the remaining places.
const GOOD_SRC = /reuters|associated press|\bap news\b|apnews|bbc|al jazeera|guardian|financial times|\bft\b|new york times|nytimes|washington post|bloomberg|telegraph|economist|france ?24|\bdw\b|deutsche welle|le monde|le figaro|cnn|npr|politico|foreign policy|foreign affairs|axios|the times|independent|sky news|abc news|abc\.net|cbc|scmp|south china morning|nikkei|irish times|intelligence online|africa confidential|the hindu|times of india|dawn|straits times|japan times|korea herald|al-monitor|middle east eye|the national|haaretz|times of israel|jerusalem post|euronews|rfi|voa|radio free europe|rferl|un news|news\.un\.org|the diplomat|devex|east asia forum|chatham house|crisis group|council on foreign relations|atlantic council|brookings|cfr\.org|wsj|wall street journal|the hill|newsweek|time magazine|forbes|channel 4|itv news|rte|ap\b|afp|agence france|anadolu|tass|xinhua|kyodo|yonhap|ansa|efe|dpa|spiegel|zeit|el pais|la nacion|folha|globo|mail & guardian|daily maverick|premium times|the east african|nation africa|the citizen|jeune afrique|allafrica|reliefweb|the new humanitarian|global voices|rest of world|semafor|vox|the atlantic|new yorker|vice news|the conversation/i;
const GEO_TTL = /\b(government|president|prime minister|minister|ministry|parliament|election|elections|vote|coup|army|military|troops|war|conflict|ceasefire|attack|attacks|strike|strikes|border|treaty|sanction|sanctions|tariff|trade|aid|talks|summit|diplomat\w*|ambassador|embassy|un|united nations|nato|eu|security|refugee\w*|migrants?|protest\w*|court|law|policy|economy|budget|imf|world bank|energy|oil|gas|pipeline|taliban|regime|opposition|rebels?|militants?|terror\w*|recogni\w+|relations|cooperation|agreement|deal|investment|kabul|beijing|moscow|washington|brussels)\b/i;
const score = it => (GOOD_SRC.test(it.s || "") ? 3 : 0) + (GEO_TTL.test(it.t || "") ? 2 : 0);
const isBad = it => BAD_SRC.test(it.s || "") || BAD_URL.test(it.u || "") || BAD_TTL.test(it.t || "");
const isSport = it => SPORT_SRC.test(it.s || "") || SPORT_URL.test(it.u || "") || SPORT_TTL.test(it.t || "");
const toks = (s, drop) => new Set(s.toLowerCase().replace(/[^a-z0-9À-ɏ ]+/g, " ").split(/\s+/).filter(w => w.length > 3 && !STOP.has(w) && !drop.has(w)));
const overlap = (a, b) => { if (!a.size || !b.size) return 0; let n = 0; for (const k of a) if (b.has(k)) n++; return n / Math.min(a.size, b.size); };

export function pick3(items, name, limit = 3, pair = null) {
  const q = pair ? pair.join(" OR ") : (QUERY[name] || name);
  const terms = q.replace(/[()]/g, "").split(/\s+OR\s+/).map(t => t.trim().replace(/^"|"$/g, "").toLowerCase());
  terms.push(name.toLowerCase().replace(/^the /, ""));
  const drop = new Set(terms.join(" ").replace(/[^a-z0-9 ]+/g, " ").split(/\s+/));
  const seen = new Set(), pool = [];
  for (const it of items) {
    const k = it.t.toLowerCase().trim();
    if (k.length < 20 || seen.has(k) || isSport(it) || isBad(it) || (pair && !PAIR_OK.test(it.t))) continue;
    seen.add(k); it._k = toks(it.t, drop); it._on = terms.some(m => it.t.toLowerCase().includes(m)); pool.push(it);
  }
  pool.forEach((p, i) => { p._r = score(p) * 1000 - i; });   // best sources and on-topic headlines first, then the order the search gave
  pool.sort((a, b) => b._r - a._r);
  const on = pool.filter(p => p._on), use = on.length >= 3 ? on : pool, out = [], srcs = new Set();
  for (const [lim, strict] of [[0.34, true], [0.6, false]]) {
    for (const it of use) {
      if (out.length >= limit || out.includes(it)) continue;
      if (strict && srcs.has(it.s)) continue;
      if (out.some(o => overlap(it._k, o._k) >= lim)) continue;
      out.push(it); srcs.add(it.s);
    }
  }
  return out.map(({ t, u, s, d }) => ({ t, u, s, d }));
}

const decode = s => s.replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&amp;/g, "&").trim();
const tag = (x, n) => { const m = new RegExp("<" + n + "[^>]*>([\\s\\S]*?)</" + n + ">").exec(x); return m ? decode(m[1]) : ""; };

export function parseRss(xml) {
  const out = [];
  for (const m of xml.matchAll(/<item>([\s\S]*?)<\/item>/g)) {
    let title = tag(m[1], "title"), src = tag(m[1], "source");
    const i = title.lastIndexOf(" - ");
    if (i > 0 && (!src || title.endsWith(" - " + src))) { src = src || title.slice(i + 3); title = title.slice(0, i); }
    let d = ""; try { d = new Date(tag(m[1], "pubDate")).toISOString().slice(0, 16) + "Z"; } catch (e) {}
    let link = tag(m[1], "link");
    const bu = /[?&]url=([^&]+)/.exec(link); if (bu && /bing\.com/.test(link)) { try { link = decodeURIComponent(bu[1]); } catch (e) {} }
    src = src || tag(m[1], "News:Source");
    if (title && link) out.push({ t: title, u: link, s: src || "Google News", d });
  }
  return out;
}

const UA = { headers: { "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36", "Accept-Language": "en-GB,en;q=0.9" } };
const get = async (u) => { const r = await fetch(u, { ...UA, signal: AbortSignal.timeout(6000) }); if (!r.ok) throw new Error(new URL(u).hostname + " " + r.status); return r.text(); };

function gather(name, other) {
  const q = other ? '"' + name + '" "' + other + '"' : (QUERY[name] || name), days = other ? 7 : 2, errs = [], pool = [];
  const srcs = [
    async () => parseRss(await get("https://news.google.com/rss/search?q=" + encodeURIComponent(q + " when:" + days + "d") + "&hl=en-GB&gl=GB&ceid=GB:en")),
    async () => parseRss(await get("https://www.bing.com/news/search?q=" + encodeURIComponent(q) + "&format=rss&setlang=en-GB&qft=sortbydate%3d%221%22")),
    async () => { const j = JSON.parse(await get("https://api.gdeltproject.org/api/v2/doc/doc?query=" + encodeURIComponent(q + " sourcelang:english") + "&mode=artlist&maxrecords=75&format=json&sort=datedesc&timespan=" + (other ? 14 : 3) + "d")); return (j.articles || []).map(a => ({ t: a.title, u: a.url, s: a.domain, d: a.seendate })); }
  ];
  // Google News comes first: it ranks by relevance and carries the established outlets. Bing and GDELT, which sort by date and
  // pick up syndicated and social posts, are only asked when Google gives too few usable headlines.
  const usable = items => items.filter(it => !isBad(it) && !isSport(it)).length;
  return (async () => {
    const pool = [];
    try { pool.push(...await srcs[0]()); } catch (e) { errs.push(String(e.message || e)); }
    if (usable(pool) >= 6) return pool;
    const rest = await Promise.allSettled([srcs[1](), srcs[2]()]);
    rest.forEach(r => { if (r.status === "fulfilled") pool.push(...r.value); else errs.push(String(r.reason && r.reason.message || r.reason)); });
    if (!pool.length) throw new Error(errs.join(" | "));
    return pool;
  })();
}

export default {
  async fetch(req, env, ctx) {
    if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
    const url = new URL(req.url), name = (url.searchParams.get("c") || "").trim().slice(0, 80), other = (url.searchParams.get("d") || "").trim().slice(0, 80);
    if (!name) return new Response(JSON.stringify({ error: "missing c" }), { status: 400, headers: CORS });
    const cache = caches.default, key = new Request(url.origin + "/?c=" + encodeURIComponent(name) + (other ? "&d=" + encodeURIComponent(other) : ""));
    const hit = await cache.match(key); if (hit) return hit;
    let items;
    try { items = await gather(name, other); }
    catch (e) { return new Response(JSON.stringify({ error: String(e.message || e) }), { status: 502, headers: CORS }); }
    const body = JSON.stringify({ updated: new Date().toISOString().slice(0, 16) + "Z", items: other ? pick3(items, name, 5, [name.toLowerCase(), other.toLowerCase()]) : pick3(items, name), pair: !!other });
    const res = new Response(body, { headers: { ...CORS, "Cache-Control": "public, max-age=900" } });
    ctx.waitUntil(cache.put(key, res.clone()));
    return res;
  }
};
