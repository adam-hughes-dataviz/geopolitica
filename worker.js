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
const SPORT_SRC = /sport|espn|cricbuzz|cricinfo|goal\.com|bleacher|athletic|onefootball|fox ?sports|yahoo sports|dazn|eurosport/i;
const SPORT_URL = /\/sports?(\/|-|\.)|sports\.|\/cricket|\/football|\/soccer|\/rugby|\/tennis|\/golf/i;
const SPORT_TTL = /\b(cricket|football|footballer|soccer|rugby|tennis|golf|golfer|pga|lpga|nba|nfl|nhl|mlb|fifa|uefa|concacaf|conmebol|ipl|t20|odi|wicket|wickets|batsman|bowler|goalkeeper|striker|olympic|olympics|paralympic|premier league|champions league|la liga|world cup|wwc|u-?17|u-?20|u-?21|asia cup|grand slam|formula (1|one)|f1|motogp|grand prix|athlete|athletes|medal|fixture|squash|hockey|kabaddi|wrestler|wrestling|boxer|boxing|ufc|mma|esports|surf|surfing|surfer|netball|basketball|baseball|volleyball|cycling|marathon|sprinter|championship|championships|round of 16|knockout|playoffs?|midfielder)\b/i;
const PAIR_OK = /\b(trade|trading|tariff|tariffs|sanction|sanctions|embargo|export|exports|import|imports|investment|invest|treaty|agreement|accord|deal|talks|negotiat\w*|summit|visit|visits|diplomat\w*|ambassador|embassy|consul\w*|foreign minister|foreign ministry|prime minister|president|minister|government|parliament|border|military|army|navy|troops|defen[cs]e|security|war|conflict|attack|strike|missile|drone|ceasefire|peace|alliance|nato|brics|asean|g20|g7|un|united nations|migration|migrants|refugees|visa|energy|oil|gas|climate|cooperation|partnership|relations|tensions|dispute|espionage|spy)\b/i;
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
    if (k.length < 20 || seen.has(k) || isSport(it) || (pair && !PAIR_OK.test(it.t))) continue;
    seen.add(k); it._k = toks(it.t, drop); it._on = terms.some(m => it.t.toLowerCase().includes(m)); pool.push(it);
  }
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
  // All three sources run at once. Finish as soon as enough stories have arrived, or when every source has answered.
  return new Promise((res, rej) => {
    let left = srcs.length;
    srcs.forEach(f => f().then(items => { pool.push(...items); if (pool.length >= 12) res(pool); }).catch(e => errs.push(String(e.message || e))).finally(() => {
      if (--left === 0) pool.length ? res(pool) : rej(new Error(errs.join(" | ")));
    }));
  });
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
