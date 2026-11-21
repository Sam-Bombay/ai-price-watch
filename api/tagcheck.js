// Hosted tag-layer check — the free, no-install version of tagcheck/check.py.
// GET /api/tagcheck?url=https://example.com
// Read-only: fetches the page as served now, lists the third-party tag bundles it loads,
// hashes each one, and reports the published 16 Nov 2026 Optimizely indicators.
// A clean result is not a clearance. It cannot say what was served on 16 Nov.

const crypto = require('crypto');

const IOC_DOMAINS = [
  'pay-relay.wordpressadmin001.workers.dev',
  'pay-cloud.online', 'pay.pay-cloud.online',
  '1688360.cc', 'webshell.lol', 'linkforge.cc',
  '5vobauua3ojpklx.icu', 'eil786npto9u5bq.icu', 'l7bcsnwc7nzr3uo.icu',
  'je4ft3gn8vxudum.icu', 'q1ls1ho9x7wsxlu.icu', 'ios-hack.icu',
  'p55abnw2pnsz0bo.icu', '1y69gy2mdzaltz1.icu', 'gm38duxoihbmy5o.icu',
];
const IOC_MARKERS = ['window._k7', 'window.__k7b', 'data-channel-code="02111110"'];
const IOC_SHA256 = [
  '814a963c0da480e2449d9b6664480156e1cd6d731014117401bf635badec3a0f',
  'f7b84b9a94f749f8ced3f0112d0a66894e8bbc3b4aa5592021d1b8976a9bad40',
];
const TAG_HOSTS = [
  'optimizely.com', 'confiant-integrations.net', 'jscrambler.com',
  'googletagmanager.com', 'kissmetrics.com', 'storifyme.com',
  'minutemedia', 'minute-media', 'linkforge.cc',
];
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 tagcheck/2.0';

function normalize(raw) {
  let u = String(raw || '').trim();
  if (!u) return null;
  if (!/^https?:\/\//i.test(u)) u = 'https://' + u;
  try { const p = new URL(u); return (p.protocol === 'http:' || p.protocol === 'https:') ? p : null; }
  catch { return null; }
}

async function get(url, timeoutMs = 12000) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { headers: { 'User-Agent': UA, Accept: '*/*' }, signal: ctl.signal, redirect: 'follow' });
    const buf = Buffer.from(await r.arrayBuffer());
    return { ok: true, status: r.status, finalUrl: r.url, headers: r.headers, buf };
  } catch (e) {
    return { ok: false, error: String(e && e.message || e) };
  } finally { clearTimeout(t); }
}

function cspGrade(csp) {
  if (!csp) return { grade: 'NONE', note: 'no Content-Security-Policy published' };
  const s = csp.toLowerCase();
  const m = s.match(/script-src([^;]*)/);
  if (!m) return { grade: 'NO-SCRIPT-SRC', note: 'CSP present but does not set script-src, so it does not restrict script origins' };
  const dir = m[1];
  if (/'unsafe-inline'/.test(dir) && /'unsafe-eval'/.test(dir)) return { grade: 'WEAK', note: "script-src allows 'unsafe-inline' and 'unsafe-eval'" };
  if (/\*/g.test(dir)) return { grade: 'WEAK', note: 'script-src uses a wildcard origin' };
  const hosts = (dir.match(/https?:\/\/[^\s'"]+/g) || []).filter(h => !TAG_HOSTS.some(t => h.includes(t)));
  if (hosts.length === 0) return { grade: 'STRONG', note: 'script-src is an allow-list with no tag-platform origin; an outside skimmer domain would be blocked' };
  return { grade: 'WEAK', note: 'script-src allows hosts beyond the site\'s own origin (' + hosts.slice(0, 4).join(', ') + ')' };
}

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 'no-store');
  const target = normalize(req.query && req.query.url);
  if (!target) {
    res.status(400).json({ error: 'Pass ?url=https://example.com' });
    return;
  }
  if (/^(localhost|127\.|10\.|192\.168\.|169\.254\.|\[::1\])/i.test(target.hostname)) {
    res.status(400).json({ error: 'Refusing to fetch a private address' });
    return;
  }

  const page = await get(target.href, 15000);
  if (!page.ok) {
    res.status(502).json({ url: target.href, error: 'could not fetch page: ' + page.error });
    return;
  }
  const html = page.buf.toString('utf8');
  const csp = page.headers.get('content-security-policy') || '';

  // every script/link/iframe src on the page
  const refs = new Set();
  const re = /(?:src|href)\s*=\s*["']([^"']+)["']/gi;
  let m;
  while ((m = re.exec(html))) {
    let u = m[1].trim();
    if (u.startsWith('//')) u = 'https:' + u;
    if (!/^https?:\/\//i.test(u)) continue;
    refs.add(u);
  }
  const tagBundles = [...refs].filter(u => TAG_HOSTS.some(h => {
    try { return new URL(u).hostname.includes(h); } catch { return false; }
  }));

  const bundles = [];
  for (const url of tagBundles.slice(0, 6)) {
    const f = await get(url, 12000);
    if (!f.ok) { bundles.push({ url, error: f.error }); continue; }
    const sha = crypto.createHash('sha256').update(f.buf).digest('hex');
    const text = f.buf.toString('utf8');
    const hits = IOC_MARKERS.filter(mk => text.includes(mk));
    const domainHits = IOC_DOMAINS.filter(d => text.includes(d));
    bundles.push({
      url, status: f.status, bytes: f.buf.length, sha256: sha,
      known_bad_hash: IOC_SHA256.includes(sha),
      indicator_markers: hits, indicator_domains: domainHits,
    });
  }

  const pageDomainHits = IOC_DOMAINS.filter(d => html.toLowerCase().includes(d));
  const pageMarkerHits = IOC_MARKERS.filter(mk => html.includes(mk));
  const badBundles = bundles.filter(b => b.known_bad_hash || (b.indicator_markers || []).length || (b.indicator_domains || []).length);

  let verdict;
  if (pageDomainHits.length || pageMarkerHits.length || badBundles.length) verdict = 'REVIEW NOW';
  else if (tagBundles.length === 0) verdict = 'NO TAG BUNDLE ON THIS PAGE';
  else verdict = 'NO PUBLISHED INDICATOR FOUND';

  res.status(200).json({
    checked_at: new Date().toISOString(),
    requested: target.href,
    fetched: page.finalUrl,
    http_status: page.status,
    verdict,
    csp: { present: !!csp, ...cspGrade(csp), raw_length: csp.length },
    tag_bundles_on_page: tagBundles.slice(0, 6),
    bundles,
    page_indicators: { domains: pageDomainHits, markers: pageMarkerHits },
    limits: 'Reads the page as served now. Cannot report what was served on 16 Nov 2026, and cannot see a loader pointing at an unpublished domain. A clean result is not a clearance.',
  });
};
