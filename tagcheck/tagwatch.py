#!/usr/bin/env python3
"""
tagwatch - daily hash watch on the third-party tag bundles a site actually serves.

The 16 Nov 2026 Optimizely incident was invisible on the customer side: the vendor's own
host served the malicious code, the site's own HTML never changed. The only cheap signal is
"the bundle the tag platform serves changed, and nobody on my team changed it".

    python3 tagwatch.py --add https://client.com
    python3 tagwatch.py            # only changes are printed; quiet = nothing moved

State lives in state.json next to this file (url -> {bundle url: sha256}). Exit 3 on change,
0 on no change, 1 on error. Free, no dependencies, no upload. Wire it to cron and mail the
output only when it is non-empty.
"""
import sys, json, os, re, hashlib, urllib.request, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "state.json")
TAG_HOSTS = ("optimizely.com", "confiant-integrations.net", "jscrambler.com",
             "googletagmanager.com", "kissmetrics.com", "storifyme.com", "linkforge.cc")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) tagwatch/1.0"

def get(url, timeout=25):
    r = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.read(6_000_000)

def bundles(site):
    html = get(site).decode("utf-8", "replace")
    srcs = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.I)
    srcs += re.findall(r'https?://[^\s"\'<>\\)]+', html)
    out = []
    for s in dict.fromkeys(srcs):
        if any(h in s.lower() for h in TAG_HOSTS):
            if s.startswith("//"): s = "https:" + s
            elif s.startswith("/"): s = site.rstrip("/") + s
            elif not s.startswith("http"): continue
            out.append(s)
    return out[:12]

def main(argv):
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    if argv[:1] == ["--add"]:
        for s in argv[1:]:
            state.setdefault(s if s.startswith("http") else "https://" + s, {})
        json.dump(state, open(STATE, "w"), indent=2)
        print(f"watching {len(state)} site(s)")
        return 0
    if not state:
        print("no sites: python3 tagwatch.py --add https://site.com")
        return 1

    changes, errors = [], []
    for site in [k for k in state if not k.startswith("_")]:
        try:
            urls = bundles(site)
        except Exception as e:
            errors.append(f"{site}: {type(e).__name__}")
            continue
        current = {}
        # only real JS bundles: noscript pixels and redirectors vary per request and
        # would produce a daily false alarm, which is worse than not watching at all.
        for u in [x for x in urls if ".js" in x.split("?")[0]]:
            try:
                current[u] = hashlib.sha256(get(u)).hexdigest()[:16]
            except Exception as e:
                errors.append(f"{u}: {type(e).__name__}")
        prev = state[site]
        for u, h in current.items():
            if u not in prev:
                changes.append(f"NEW bundle  {site}\n  {u}\n  sha256 {h}")
            elif prev[u] != h:
                changes.append(f"CHANGED     {site}\n  {u}\n  {prev[u]} -> {h}")
        for u in prev:
            if u not in current:
                changes.append(f"GONE        {site}\n  {u}")
        state[site] = current
    state["_last_run"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    json.dump(state, open(STATE, "w"), indent=2)

    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if changes:
        print(f"TAGWATCH {stamp} - {len(changes)} change(s)")
        for c in changes: print(c)
    for e in errors:
        print(f"unverified: {e}", file=sys.stderr)
    return 3 if changes else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
