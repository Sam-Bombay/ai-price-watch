#!/usr/bin/env python3
"""Sample inventory: reads the public home page of a list of major US retail / travel /
telco / financial sites and records which tag-platform project JavaScript it loads and
whether its CSP would have blocked an outside loader. Read-only GETs. Output: JSON + HTML.
This is a labelled SAMPLE, not a complete index of any company's estate."""
import sys, os, json, datetime, concurrent.futures as cf

sys.path.insert(0, "/Users/sambombay/money-ideas/tracker/tagcheck")
from check import check_site  # noqa: E402

DOMAINS = [
    "www.nike.com", "www.rei.com", "www.target.com", "www.walmart.com", "www.bestbuy.com",
    "www.homedepot.com", "www.lowes.com", "www.sephora.com", "www.nordstrom.com", "www.macys.com",
    "www.kohls.com", "www.wayfair.com", "www.chewy.com", "www.etsy.com", "www.godaddy.com",
    "www.stamps.com", "www.mattressfirm.com", "www.build.com", "www.wendys.com", "www.dominos.com",
    "www.t-mobile.com", "www.verizon.com", "www.att.com", "www.allstate.com", "www.progressive.com",
    "www.geico.com", "www.usbank.com", "www.marriott.com", "www.hilton.com", "www.hyatt.com",
    "www.southwest.com", "www.delta.com", "www.united.com", "www.alaskaair.com", "www.subaru.com",
    "www.ford.com", "www.toyota.com", "www.honda.com", "www.ariat.com", "www.scheels.com",
    "www.cinnabon.com", "www.smartsheet.com", "www.mixpanel.com", "www.typeform.com",
    "www.hootsuite.com", "www.gitlab.com", "www.smartsheet.com", "www.crocs.com",
]


def run(domains):
    out = []
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(check_site, d if d.startswith("http") else "https://" + d): d for d in domains}
        for f in cf.as_completed(futs):
            try:
                out.append(f.result())
            except Exception as e:
                out.append({"site": futs[f], "verdict": "ERROR", "note": str(e)})
    order = {d: i for i, d in enumerate(domains)}
    return sorted(out, key=lambda r: order.get(r["site"], 999))


def summarise(rows):
    s = {"checked": len(rows), "tag_host": 0, "clean": 0, "indicator": 0, "csp_none": 0,
         "csp_weak": 0, "csp_strong": 0, "unreachable": 0}
    for r in rows:
        if r.get("verdict") in ("ERROR",):
            s["unreachable"] += 1
        elif r.get("tag_bundles"):
            s["tag_host"] += 1
        if any(f.get("kind") != "unverified" and "IOC" in str(f.get("kind")) for f in r.get("findings", [])):
            s["indicator"] += 1
        g = (r.get("csp") or {}).get("grade")
        if g == "NONE":
            s["csp_none"] += 1
        elif g == "WEAK":
            s["csp_weak"] += 1
        elif g == "STRONG":
            s["csp_strong"] += 1
    return s


HTML = """<!doctype html><meta charset=utf-8><title>Tag-layer exposure sample - {date}</title>
<style>body{{font:15px/1.5 -apple-system,Helvetica,Arial;margin:32px;max-width:1000px;color:#111}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid #e5e5e5;vertical-align:top}}
th{{background:#fafafa}}code{{font-size:12px}}.g{{font-weight:600}}</style>
<h1>Tag-layer exposure sample &mdash; {date}</h1>
<p>Read-only check of the public home page of {checked} major US retail, travel, telco and finance
sites, {ts}. It records which tag-platform project JavaScript each page loads and how its
Content-Security-Policy is set. <b>This is a labelled sample</b> of what the public pages served at
that moment; it is not a complete inventory of any company's estate, and a site that loads a tag
platform is not by itself compromised.</p>
<p><b>{tag_host}</b> of {checked} load project JavaScript from a tag host on the home page.
<b>{csp_none}</b> publish no Content-Security-Policy and <b>{csp_weak}</b> publish one that still permits an
outside script origin; <b>{csp_strong}</b> publish a policy that would block one.
<b>{indicator}</b> showed a published malicious indicator.</p>
<table><tr><th>Site</th><th>Tag bundles on page</th><th>CSP</th><th>Indicator</th></tr>
{rows}
</table>
<p style="color:#666;font-size:12px">Method: HTTP GET, no authentication, no crawling behind
logins, one request per page plus one per script bundle. Produced by Aria, Sam Bombay's AI
assistant, using the free checker at
https://sam-bombay.github.io/ai-price-watch/tagcheck/.</p>"""


def main():
    rows = run(DOMAINS)
    s = summarise(rows)
    now = datetime.datetime.now().astimezone()
    date = now.strftime("%d %b %Y")
    ts = now.strftime("%Y-%m-%d %H:%M %Z")
    base = "/Users/sambombay/money-ideas/tracker/tagcheck/inventory"
    os.makedirs(base, exist_ok=True)
    with open(f"{base}/sample-{now:%Y%m%d-%H%M}.json", "w") as f:
        json.dump({"generated": ts, "summary": s, "rows": rows}, f, indent=1)
    trs = []
    for r in rows:
        bundles = "<br>".join(f"<code>{b[:90]}</code>" for b in (r.get("tag_bundles") or [])[:3]) or "&mdash;"
        g = (r.get("csp") or {}).get("grade", "?")
        ind = "yes" if any("IOC" in str(f.get("kind", "")) for f in r.get("findings", [])) else "&mdash;"
        trs.append(f"<tr><td>{r['site']}</td><td>{bundles}</td><td class=g>{g}</td><td>{ind}</td></tr>")
    with open(f"{base}/index.html", "w") as f:
        f.write(HTML.format(date=date, ts=ts, rows="\n".join(trs), **s))
    print(json.dumps(s, indent=1))
    for r in rows:
        print(f"{r['site']:28} {(r.get('csp') or {}).get('grade','?'):6} {len(r.get('tag_bundles') or [])} bundles")


if __name__ == "__main__":
    main()
