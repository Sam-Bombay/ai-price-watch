#!/usr/bin/env python3
"""
tagcheck - third-party tag-layer compromise check (OPTIMJACK / Optimizely, Nov 2026)

Read-only. Fetches the page, finds every third-party tag bundle it loads, fetches those
bundles, and searches them for the indicators published for the 16 Nov 2026 Optimizely
injection. Nothing is written except the report file, nothing is uploaded.

Usage:
    python3 check.py https://example.com [https://second.com ...]
    python3 check.py --list sites.txt

Exit codes: 0 = no indicator found, 2 = at least one site needs review, 1 = could not run.

Limits, stated because they matter: this checks the page as served NOW. It cannot tell you
what was served on 16 November 2026, and it will not catch a loader pointing at a domain
that is not in the published indicator list. A clean result is not a clearance.
"""
import sys, re, json, urllib.request, urllib.error, datetime, hashlib

IOC_DOMAINS = [
    # vendor-confirmed, Optimizely's own incident report, 17 Nov 2026 (section 10)
    "pay-relay.wordpressadmin001.workers.dev",   # skimmer exfiltration endpoint
    "pay-cloud.online", "pay.pay-cloud.online",  # attacker infrastructure hosting the skimmer
    # Report URI / OPTIMJACK analysis, 16-17 Nov 2026
    "1688360.cc", "webshell.lol", "linkforge.cc",
    "5vobauua3ojpklx.icu", "eil786npto9u5bq.icu", "l7bcsnwc7nzr3uo.icu",
    "je4ft3gn8vxudum.icu", "q1ls1ho9x7wsxlu.icu", "ios-hack.icu",
    "p55abnw2pnsz0bo.icu", "1y69gy2mdzaltz1.icu", "gm38duxoihbmy5o.icu",
]
IOC_MARKERS = ["window._k7", "window.__k7b", "data-channel-code=\"02111110\""]
IOC_SHA256 = [
    "814a963c0da480e2449d9b6664480156e1cd6d731014117401bf635badec3a0f",  # track.js 17:13 UTC 16 Nov
    "f7b84b9a94f749f8ced3f0112d0a66894e8bbc3b4aa5592021d1b8976a9bad40",  # track.js 17:57 UTC 16 Nov
]
# Hosts that serve tag-layer / experiment / analytics bundles. A page loading one of these
# has an attack surface that its own code review does not cover.
TAG_HOSTS = ("optimizely.com", "confiant-integrations.net", "jscrambler.com",
             "googletagmanager.com", "kissmetrics.com", "storifyme.com",
             "minute-media", "minutemedia", "linkforge.cc")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 tagcheck/1.0"

def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(4_000_000)
        return r.geturl(), raw.decode("utf-8", "replace")

def fetch_page(url, timeout=20):
    """Page fetch that also returns response headers and the raw bytes (for hashing)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read(4_000_000)
        hdrs = {k.lower(): v for k, v in r.headers.items()}
        return r.geturl(), raw, hdrs

def csp_grade(headers, html):
    """How much a strong CSP would have stopped this loader. Stated as evidence, not advice:
    Optimizely's own report says sites with a strong script-src were protected because the
    skimmer loaded from an outside domain."""
    csp = headers.get("content-security-policy", "") or headers.get(
        "content-security-policy-report-only", "")
    if not csp:
        for m in re.finditer(r'<meta[^>]+http-equiv=["\']content-security-policy["\'][^>]+content=["\']([^"\']+)',
                             html, re.I):
            csp = m.group(1)
            break
    if not csp:
        return "NONE", "no Content-Security-Policy header or meta tag found"
    low = csp.lower()
    if "script-src" not in low and "default-src" not in low:
        return "WEAK", "CSP present but sets no script-src or default-src"
    directive = "script-src" if "script-src" in low else "default-src"
    allows_any = "*" in csp.split(directive, 1)[1].split(";")[0]
    if allows_any or "https:" in csp.split(directive, 1)[1].split(";")[0]:
        return "WEAK", f"{directive} allows any https origin, so an outside loader would still run"
    return "STRONG", f"{directive} restricted to named origins; an outside loader from a new domain would be blocked"

def scripts(html):
    out = []
    for m in re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.I):
        out.append(m.group(1))
    return out

def check_site(url):
    rec = {"site": url, "checked_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
           "verdict": "ERROR", "tag_bundles": [], "findings": [], "note": ""}
    try:
        final, raw, hdrs = fetch_page(url)
        html = raw.decode("utf-8", "replace")
    except Exception as e:
        rec["note"] = f"could not fetch: {type(e).__name__}: {e}"
        return rec
    rec["final_url"] = final
    rec["html_sha256"] = hashlib.sha256(html.encode()).hexdigest()
    grade, why = csp_grade(hdrs, html)
    rec["csp"] = {"grade": grade, "detail": why}

    srcs = scripts(html)
    # tag bundles are often injected from an inline snippet rather than written as a
    # literal <script src>, so sweep the whole document for tag-host URLs too.
    all_urls = re.findall(r'https?://[^\s"\'<>\\)]+', html)
    candidates = list(dict.fromkeys(srcs + all_urls))
    # only executable bundles matter here; CMS image/CDN assets on a tag host are noise and
    # made earlier reports unreadable
    _asset_ext = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".woff", ".woff2", ".ico", ".pdf")
    def _is_script(u):
        base = u.split("?")[0].split("#")[0].lower()
        return not base.endswith(_asset_ext)
    tag_srcs = [s for s in candidates if any(h in s.lower() for h in TAG_HOSTS) and _is_script(s)]
    inline_tag_mention = any(h in html.lower() for h in ("optimizely", "criteo", "confiant", "jscrambler"))
    rec["tag_bundles"] = tag_srcs[:20]
    rec["scripts_total"] = len(srcs)

    # inline indicators in the page itself
    for d in IOC_DOMAINS:
        if d in html:
            rec["findings"].append({"where": "page html", "match": d, "kind": "published IOC domain"})
    for m in IOC_MARKERS:
        if m in html:
            rec["findings"].append({"where": "page html", "match": m, "kind": "payload marker"})

    for s in tag_srcs[:12]:
        absolute = urllib.parse.urljoin(final, s) if s.startswith("/") else s
        if not absolute.startswith("http"):
            absolute = "https://" + absolute
        try:
            _, raw_b, _ = fetch_page(absolute)
            body = raw_b.decode("utf-8", "replace")
        except Exception as e:
            rec["findings"].append({"where": absolute, "match": f"fetch failed: {type(e).__name__}",
                                    "kind": "unverified"})
            continue
        bhash = hashlib.sha256(raw_b).hexdigest()
        rec.setdefault("bundle_hashes", []).append({"url": absolute, "sha256": bhash})
        if bhash in IOC_SHA256:
            rec["findings"].append({"where": absolute, "match": bhash,
                                    "kind": "exact byte match to a known malicious track.js build"})
        for d in IOC_DOMAINS:
            if d in body:
                rec["findings"].append({"where": absolute, "match": d, "kind": "published IOC domain in tag bundle"})
        for m in IOC_MARKERS:
            if m in body:
                rec["findings"].append({"where": absolute, "match": m, "kind": "payload marker in tag bundle"})
        # loader shape: atob() obscuring a .cc/.icu host, or a script element built for an
        # unknown external host from inside a tag bundle
        for m in re.finditer(r'atob\([^)]{0,200}\)', body):
            if re.search(r'/\.(cc|icu)/', m.group(0)):
                rec["findings"].append({"where": absolute, "match": m.group(0)[:120],
                                        "kind": "base64 loader toward .cc/.icu host"})
        rec["tag_bundles"][rec["tag_bundles"].index(s)] = f"{s} ({len(body)} bytes)"

    hard = [f for f in rec["findings"] if f["kind"] != "unverified"]
    rec["verdict"] = "REVIEW" if hard else ("NO_INDICATOR" if tag_srcs or srcs else "NO_SCRIPTS")
    if not tag_srcs:
        rec["note"] = ("no tag-host bundle URL found on this page"
                       + ("; a tag platform is named in the page but its bundle is loaded by "
                          "JavaScript after render, so check it in a browser's network tab"
                          if inline_tag_mention else "")
                       + ". If the site runs experiments on other templates, check those paths too")
    return rec

def main(argv):
    if not argv:
        print(__doc__)
        return 1
    sites = argv
    if argv[0] == "--list":
        sites = [l.strip() for l in open(argv[1]) if l.strip() and not l.startswith("#")]
    import urllib.parse  # noqa: F401  (used in check_site)
    results = []
    for s in sites:
        if not s.startswith("http"):
            s = "https://" + s
        r = check_site(s)
        results.append(r)
        print(f"\n{r['site']}  ->  {r['verdict']}  CSP={r.get('csp', {}).get('grade', '?')}")
        if r.get("csp"):
            print(f"    csp: {r['csp']['detail']}")
        if r["tag_bundles"]:
            for b in r["tag_bundles"]:
                print(f"    tag bundle: {b}")
        for f in r["findings"]:
            print(f"    ! {f['kind']}: {f['match']}  [{f['where']}]")
        if r["note"]:
            print(f"    note: {r['note']}")
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = f"tagcheck-{stamp}.json"
    with open(out, "w") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nreport: {out}")
    print("This reads the page as served now. It cannot reconstruct what was served on 16 Nov 2026.")
    return 2 if any(r["verdict"] == "REVIEW" for r in results) else 0

if __name__ == "__main__":
    import urllib.parse
    sys.exit(main(sys.argv[1:]))
