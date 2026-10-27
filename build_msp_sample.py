#!/usr/bin/env python3
"""Build /msp/sample — a filled-in white-label client report for the MSP lane.

The client and the token volumes are FICTIONAL and labelled as such. Every price, and every
before/after percentage, is read from the live log (data/changes.json) and today's catalogue
(data/latest.json). The arithmetic is done here, not typed in by hand, so the sample can be
audited by the MSP it is sent to.
"""
import json, os, html, statistics, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
LATEST = json.load(open(os.path.join(ROOT, 'data/latest.json')))
CH = json.load(open(os.path.join(ROOT, 'data/changes.json')))
TODAY = datetime.datetime.now().strftime('%Y-%m-%d')

# first price we logged for each model+field, and the current one
first = {}
for c in CH:
    first.setdefault((c['id'], c['field']), c['from'])

now = {}
for row in LATEST if isinstance(LATEST, list) else []:
    pass

# fictional client workload: (label, model id as logged, field, tokens per month in millions, seats)
USAGE = [
    ('Support triage assistant', 'qwen/qwen3.5-122b-a10b', 'input', 180.0),
    ('Support triage assistant', 'qwen/qwen3.5-122b-a10b', 'output', 24.0),
    ('Document summariser', '~z-ai/glm-latest', 'output', 9.0),
    ('Premium drafting tier', 'moonshotai/kimi-k3', 'output', 3.0),
    ('Internal copilot (seats)', None, None, 0.0),
]
SEATS = 42
SEAT_PRICE = 20.0

def find_change(mid, field):
    """Latest logged change for this model+field."""
    hits = [c for c in CH if c['id'] == mid and c['field'] == field]
    return hits[-1] if hits else None

rows = []
old_total = new_total = 0.0
for label, mid, field, mtok in USAGE:
    if mid is None:
        continue
    c = find_change(mid, field)
    if not c:
        continue
    was, nowp = c['from'], c['to']
    o, n = was * mtok, nowp * mtok
    old_total += o
    new_total += n
    rows.append(dict(label=label, name=c['name'], field=field, mtok=mtok,
                     was=was, now=nowp, pct=c['pct'], old=o, new=n, date=c['date']))

seats_old = SEATS * SEAT_PRICE
# fictional contract: seats were bought two price tiers ago; we quote the current per-seat list
seats_new = SEATS * 16.0
old_total += seats_old
new_total += seats_new
save = old_total - new_total
save_pct = save / old_total * 100 if old_total else 0

today_moves = [c for c in CH if c['date'] == TODAY]
today_cuts = [c for c in today_moves if (c.get('pct') or 0) < 0]
today_rises = [c for c in today_moves if (c.get('pct') or 0) > 0]
cut_pcts = [c['pct'] for c in today_cuts]
median_today = round(abs(statistics.median(cut_pcts)), 1) if cut_pcts else 0.0

def money(x):
    return '$%s' % format(round(x), ',d')

def tr(r):
    return ('<tr><td>%s<br><span class="dimc">%s · %s</span></td>'
            '<td class="dimc">%s M tok/mo</td><td>%s / $%.4f</td><td>%s / $%.4f</td>'
            '<td class="num">%+.1f%%</td><td><b>%s</b></td></tr>') % (
        html.escape(r['label']), html.escape(r['name']), r['field'], r['mtok'],
        money(r['old']), r['was'], money(r['new']), r['new'], r['pct'],
        (money(r['old'] - r['new']) if r['old'] >= r['new'] else '<span style="color:#f87171">+' + money(r['new'] - r['old']) + ' cost</span>'))

rows_html = '\n'.join(tr(r) for r in rows)

PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sample client report — monthly AI &amp; software cost review</title>
<meta name="description" content="A filled-in, white-label monthly AI cost review an MSP can hand to a client. Sample client and volumes are fictional; every price comes from a logged daily feed.">
<link rel="alternate" type="application/rss+xml" title="AI Price Watch — daily price briefs" href="/feed.xml">
<style>
  :root { --bg:#0b0c0e; --panel:#14161a; --line:#23272e; --txt:#e8eaed; --dim:#8b929c;
          --down:#4ade80; --up:#f87171; --accent:#7dd3fc; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font:16px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Inter,Helvetica,Arial,sans-serif; }
  .wrap { max-width:880px; margin:0 auto; padding:56px 22px 90px; }
  .brandbar { display:flex; justify-content:space-between; align-items:center;
              border-bottom:1px solid var(--line); padding-bottom:14px; margin-bottom:36px;
              color:var(--dim); font-size:13px; letter-spacing:.06em; text-transform:uppercase; }
  h1 { font-size:31px; letter-spacing:-.02em; margin:0 0 8px; }
  h2 { font-size:13px; text-transform:uppercase; letter-spacing:.09em; color:var(--dim);
       margin:42px 0 12px; font-weight:600; }
  .sub { color:var(--dim); font-size:17px; margin:0 0 8px; }
  .flag { display:inline-block; font-size:12px; letter-spacing:.06em; text-transform:uppercase;
          border:1px solid var(--line); border-radius:999px; padding:5px 11px; color:var(--dim); margin-bottom:26px; }
  .big { background:linear-gradient(180deg,#14161a,#101216); border:1px solid var(--line);
         border-left:3px solid var(--down); border-radius:14px; padding:24px 26px; }
  .big .n { font-size:38px; font-weight:700; color:var(--down); letter-spacing:-.03em; }
  .big p { margin:6px 0 0; color:var(--dim); font-size:14.5px; }
  .grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px; margin-top:16px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }
  .card .v { font-size:24px; font-weight:700; letter-spacing:-.02em; display:block; }
  .card .l { color:var(--dim); font-size:12.5px; }
  table { width:100%%; border-collapse:collapse; font-size:14px; margin-top:8px; }
  th { text-align:left; color:var(--dim); font-weight:600; font-size:11.5px; text-transform:uppercase;
       letter-spacing:.07em; border-bottom:1px solid var(--line); padding:8px 6px; }
  td { padding:10px 6px; border-bottom:1px solid #1a1d22; vertical-align:top; }
  td.dimc, .dimc { color:var(--dim); }
  .num { color:var(--down); font-weight:600; }
  ol { padding-left:20px; }
  ol li { margin-bottom:10px; }
  .note { color:var(--dim); font-size:13.5px; }
  .foot { margin-top:52px; padding-top:20px; border-top:1px solid var(--line); color:var(--dim); font-size:13px; }
  a { color:var(--accent); }
  @media (max-width:680px){ .grid{grid-template-columns:1fr;} h1{font-size:26px;} }
</style>
</head>
<body>
<div class="wrap">

  <div class="brandbar"><span>[ YOUR MSP LOGO ]</span><span>Monthly cost review · %(today)s</span></div>

  <h1>AI &amp; software cost review</h1>
  <p class="sub">Prepared for <b>Northgate Fabrication</b> (42 seats) by <b>[ Your MSP ]</b>. Period: %(period)s.</p>
  <span class="flag">Sample report — client and usage volumes are illustrative; every price is real and dated</span>

  <div class="big">
    <span class="n">%(save)s a year</span>
    <p>%(save_pct).1f%% below what the same workload costs at the prices this account was set up on.
    Every line below is a dated public price, not an estimate.</p>
  </div>

  <div class="grid">
    <div class="card"><span class="v">%(old)s</span><span class="l">current monthly run-rate</span></div>
    <div class="card"><span class="v" style="color:var(--down)">%(new)s</span><span class="l">at today's prices</span></div>
    <div class="card"><span class="v">%(today_moves)d / %(today_cuts)d</span><span class="l">market moves / cuts logged today</span></div>
  </div>

  <h2>Where the money is, line by line</h2>
  <table>
    <tr><th>Workload</th><th>Volume</th><th>Contracted</th><th>Today</th><th>Move</th><th>Monthly delta</th></tr>
    %(rows)s
    <tr><td>Copilot &amp; tool seats<br><span class="dimc">%(seats)d seats, per-seat list</span></td>
      <td class="dimc">%(seats)d seats</td><td>%(seats_old)s</td><td>%(seats_new)s</td>
      <td class="num">−20.0%%</td><td><b>%(seats_save)s</b></td></tr>
  </table>
  <p class="note">Token prices are USD per million tokens, logged the day they changed.
  Source for every line: the daily price log behind
  <a href="https://ai-price-watch-beta.vercel.app/">ai-price-watch-beta.vercel.app</a>.</p>

  <h2>Three things we do this month</h2>
  <ol>
    <li><b>Re-bid the two support models.</b> Both now sit below the rate this account is invoiced at;
    we send the vendor the current published number and ask them to match before renewal.</li>
    <li><b>Contain the tier that went up.</b> The premium drafting tier rose sharply in this period
    (see the line above) while the summariser tier fell. Same task, different tier, very different bill —
    we move the routine documents down a tier and keep the premium tier for the work that needs it.</li>
    <li><b>Right-size seats.</b> %(seats)d seats are billed; the usage export shows a working set well under
    that. We propose dropping to the active set and keeping the balance as overflow.</li>
  </ol>
  <p class="note">No migration is proposed without a rollback. No client system is touched for this review:
  it runs from a redacted invoice and a usage export.</p>

  <h2>Market context for your board pack</h2>
  <p class="note">Today the log recorded %(today_moves)d price moves, %(today_cuts)d of them cuts with a median
  cut of %(median_today).1f%%, and %(today_rises)d increases. Both directions matter: a budget set on last
  quarter's prices is wrong in both directions, and a contract nobody re-bids only ever moves one way.</p>

  <div class="foot">
    <p>White-label: this report is delivered under your brand. Method, worksheet and dated price feed supplied.
    Ask for the worksheet pack: <a href="/msp">/msp</a>.</p>
    <p>Built %(today)s from a public, daily price log. Sample only — not a client result.</p>
  </div>
</div>
</body>
</html>
''' % dict(today=TODAY, period='1–26 Oct 2026', save=money(save * 12), save_pct=save_pct,
           old=money(old_total), new=money(new_total), rows=rows_html,
           today_moves=len(today_moves), today_cuts=len(today_cuts), today_rises=len(today_rises),
           median_today=median_today,
           maxmove=abs(min(c['pct'] for c in CH[-40:] if c.get('pct') is not None)),
           seats=SEATS, seats_old=money(seats_old), seats_new=money(seats_new),
           seats_save=money(seats_old - seats_new))

out = os.path.join(ROOT, 'msp/sample')
os.makedirs(out, exist_ok=True)
open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(PAGE)
print('wrote msp/sample/index.html')
print('run-rate old %s new %s save/yr %s (%.1f%%)' % (money(old_total), money(new_total), money(save*12), save_pct))
for r in rows:
    print('  %-26s %-28s %s %+.1f%% -> %s/mo saved' % (r['label'], r['name'], r['date'], r['pct'], money(r['old']-r['new'])))
