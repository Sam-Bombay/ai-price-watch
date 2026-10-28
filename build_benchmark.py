#!/usr/bin/env python3
"""Build /benchmark — the CFO page.

Every number is computed from the live OpenRouter-derived price file (data/latest.json)
and the change log (data/changes.json). Nothing is estimated or invented.

The point of the page: for a given monthly token volume, there is a 30-40x spread between
the cheapest, median and premium workhorse models on the same catalogue, same day. A CFO
cannot see that spread on a vendor invoice, which is why "we already checked AI spend"
is usually true and still wrong.
"""
import json, os, statistics, datetime, html

ROOT = os.path.dirname(os.path.abspath(__file__))
LAT = json.load(open(os.path.join(ROOT, 'data/latest.json')))
CH = json.load(open(os.path.join(ROOT, 'data/changes.json')))
MODELS = LAT['models']
UPDATED = LAT.get('updated', datetime.datetime.now().strftime('%Y-%m-%d'))
TODAY = datetime.datetime.now().strftime('%Y-%m-%d')

# workhorse class = something you can actually run a product on: 100k+ context, both prices set
WH = [m for m in MODELS if m.get('in') is not None and m.get('out') is not None
      and (m.get('ctx') or 0) >= 100000]

# monthly workloads: input tokens, output tokens, label, who this is
PROFILES = [
    (25_000_000, 3_000_000, '10-person shop', 'a support bot, some drafting, a little code help'),
    (120_000_000, 18_000_000, '40-person company', 'everyone has a seat, one product feature uses a model'),
    (500_000_000, 90_000_000, '150-person company', 'seats plus two production features and a document pipeline'),
]

def bill(m, tin, tout):
    return (tin / 1_000_000) * m['in'] + (tout / 1_000_000) * m['out']

prof_rows = []
for tin, tout, who, what in PROFILES:
    priced = sorted(((bill(m, tin, tout), m) for m in WH), key=lambda x: x[0])
    costs = [c for c, _ in priced]
    med = statistics.median(costs)
    p90 = statistics.quantiles(costs, n=10)[8]  # 90th percentile
    lo, lo_m = priced[0]
    top, top_m = priced[-1]
    prof_rows.append(dict(who=who, what=what, tin=tin, tout=tout, lo=lo, lo_m=lo_m['name'],
                          med=med, p90=p90, top=top, top_m=top_m['name'],
                          multiple=p90 / med if med else 0))

def money(v):
    if v >= 10000:
        return '${:,.0f}'.format(v)
    if v >= 100:
        return '${:,.0f}'.format(v)
    return '${:,.2f}'.format(v)

today_moves = [c for c in CH if c['date'] == TODAY]
today_cuts = sorted([c for c in today_moves if (c.get('pct') or 0) < 0], key=lambda c: c['pct'])[:6]

first_prof = prof_rows[1]
spread_words = '{:,.1f}x'.format(first_prof['multiple'])

def cut_row(c):
    return ('<tr><td>%s</td><td class="dimc">%s</td><td class="dimc">$%.4f</td><td>$%.4f</td>'
            '<td class="num">%+.1f%%</td></tr>') % (
        html.escape(c['name']), c['field'], c['from'], c['to'], c['pct'])

cuts_html = '\n'.join(cut_row(c) for c in today_cuts) or \
    '<tr><td colspan="5" class="dimc">No cuts logged today. The table below still holds.</td></tr>'

def prof_block(p):
    annual_p90 = p['p90'] * 12
    annual_med = p['med'] * 12
    return '''    <tr>
      <td><b>%s</b><br><span class="dimc">%s</span></td>
      <td class="dimc">%sM in / %sM out</td>
      <td>%s</td>
      <td>%s</td>
      <td class="hi">%s</td>
      <td class="num">%s<br><span class="dimc">yr</span></td>
    </tr>''' % (
        p['who'], p['what'], '{:,}'.format(p['tin'] // 1_000_000), '{:,}'.format(p['tout'] // 1_000_000),
        money(p['lo']), money(p['med']), money(p['p90']), money(annual_p90))

rows_html = '\n'.join(prof_block(p) for p in prof_rows)

PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI spend benchmark — what this should cost | AI Price Watch</title>
<meta name="description" content="The same monthly AI workload costs between {{lo}} and {{hi}} a month on today's catalogue. A daily-updated benchmark computed from public model prices.">
<style>
  :root { --bg:#0b0c0e; --panel:#14161a; --line:#23272e; --txt:#e8eaed; --dim:#8b929c;
          --down:#4ade80; --up:#f87171; --accent:#7dd3fc; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font:16px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Inter,Helvetica,Arial,sans-serif; }
  .wrap { max-width:880px; margin:0 auto; padding:64px 22px 90px; }
  h1 { font-size:34px; letter-spacing:-.02em; margin:0 0 10px; }
  h2 { font-size:14px; text-transform:uppercase; letter-spacing:.09em; color:var(--dim);
       margin:44px 0 14px; font-weight:600; }
  .sub { color:var(--dim); font-size:18px; margin:0 0 34px; }
  .hero { background:linear-gradient(180deg,#14161a,#101216); border:1px solid var(--line);
          border-left:3px solid var(--down); border-radius:14px; padding:24px 26px; }
  .hero b { font-size:18px; }
  .grid { display:grid; grid-template-columns:1fr 1fr 1fr 1fr; gap:14px; margin-top:18px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:18px 20px; }
  .big { font-size:26px; font-weight:700; color:var(--down); letter-spacing:-.02em; display:block; }
  .card span.lbl { color:var(--dim); font-size:13px; }
  table { width:100%; border-collapse:collapse; font-size:14.5px; margin-top:10px; }
  th { text-align:left; color:var(--dim); font-weight:600; font-size:12px; text-transform:uppercase;
       letter-spacing:.07em; border-bottom:1px solid var(--line); padding:8px 6px; }
  td { padding:11px 6px; border-bottom:1px solid #1a1d22; vertical-align:top; }
  td.dimc, span.dimc { color:var(--dim); font-size:13px; }
  td.hi { color:var(--up); font-weight:600; }
  .num { color:var(--down); font-weight:600; }
  .note { color:var(--dim); font-size:13.5px; margin-top:10px; }
  .cta { display:block; text-align:center; margin:22px 0 0; padding:16px; border-radius:12px;
         background:#e8eaed; color:#0b0c0e; font-weight:700; font-size:17px; text-decoration:none; }
  .cta.alt { background:transparent; border:1px solid var(--line); color:var(--txt);
             font-weight:600; font-size:15px; }
  .foot { margin-top:56px; padding-top:22px; border-top:1px solid var(--line); color:var(--dim); font-size:13.5px; }
  a { color:var(--accent); }
  @media (max-width:680px){ .grid{grid-template-columns:1fr 1fr;} h1{font-size:27px;} table{font-size:13px;} }
</style>
</head>
<body>
<div class="wrap">

  <h1>The same AI work is billed {{spread}} apart</h1>
  <p class="sub">A monthly benchmark, recomputed every day from published model prices.
  If your AI bill was set more than a month ago, the number on it is out of date — in both
  directions.</p>

  <div class="hero">
    <p><b>A 40-person company running {{p1tin}}M input tokens and {{p1tout}}M output tokens a
    month bills anywhere from {{p1lo}} (cheapest capable model) to {{p1top}} (90th percentile) for the same volume.</b>
    That is a {{spread}} gap on an input nobody negotiates, across {{models}} models listed
    publicly today. The median bill for that volume is {{p1med}} a month — so a company sitting at
    the top of the range is overpaying roughly {{over}} a month — {{overyr}} a year — against the middle of the market.</p>
  </div>

  <div class="grid">
    <div class="card"><span class="big">{{models}}</span><span class="lbl">models priced daily</span></div>
    <div class="card"><span class="big">{{wh}}</span><span class="lbl">workhorse class (100k+ ctx)</span></div>
    <div class="card"><span class="big">{{events}}</span><span class="lbl">price changes logged</span></div>
    <div class="card"><span class="big">{{moves}}</span><span class="lbl">moves today</span></div>
  </div>

  <h2>What a month of ordinary AI work should cost — {{updated}}</h2>
  <table>
    <tr><th>Company</th><th>Monthly volume</th><th>Cheapest workhorse</th><th>Median of market</th>
        <th>Premium (90th pct)</th><th>Annualised at premium</th></tr>
{{rows}}
  </table>
  <p class="note">Method: every one of the {{models}} models in OpenRouter's public catalogue with a
  context window of 100k tokens or more ({{wh}} of them), priced at the published rate per million
  input and output tokens, applied to the stated monthly volume. The ceiling is far higher than the
  90th percentile — the most expensive workhorse model today would bill a 40-person company
  {{topbill}} a month for the same volume. Prices change daily; this page is rebuilt each morning
  from the same log the briefs come from.</p>

  <h2>The honest caveat</h2>
  <p class="note">Cheap is not the same as equivalent. The cheapest models in this table are small,
  fast and fine for classification, extraction, drafting and support replies; they are not what you
  write a long-context agent on. The point is not "use the cheapest model" — it is that most
  companies are paying premium rates for the routine share of their traffic, and the routine share
  is usually most of it. Splitting traffic by task is where the money is.</p>

  <h2>Moves logged today ({{today}})</h2>
  <table>
    <tr><th>Model</th><th>Field</th><th>Was /M</th><th>Now /M</th><th>Change</th></tr>
{{cuts}}
  </table>

  <a class="cta" href="mailto:sambombayoffice@gmail.com?subject=AI%20cost%20audit%20%E2%80%94%20one%20redacted%20invoice&body=Hi%20Sam%20%E2%80%94%20I%20read%20the%20benchmark.%20Our%20AI%20spend%20is%20about%20%24____%20a%20month.%20Here%20is%20a%20redacted%20invoice.%20What%20is%20honestly%20cuttable%3F">Send one redacted invoice. I return the cut list in 48 hours. No call.</a>
  <a class="cta alt" href="/repricing">Or price your own re-bid first — free, no signup</a>

  <div class="foot">
    <p><a href="/">AI Price Watch</a> &middot; <a href="/repricing">re-bid</a> &middot;
    <a href="/receipts">my own audit</a> &middot; <a href="/local-stt">local transcription</a> &middot;
    <a href="/clinic">clinic</a> &middot; <a href="/feed.xml">feed</a></p>
    <p>Source: OpenRouter public model catalogue, logged daily. Prices in USD per million tokens.
    This is a factual index of published list prices, not advice, and not a quote for any vendor's
    contract. Updated {{updated}}.</p>
  </div>

</div>
</body>
</html>
'''

vals = dict(
    spread=spread_words,
    models='{:,}'.format(len(MODELS)),
    wh='{:,}'.format(len(WH)),
    events='{:,}'.format(len(CH)),
    moves='{:,}'.format(len(today_moves)),
    updated=UPDATED,
    rows=rows_html,
    cuts=cuts_html,
    today=TODAY,
    lo=money(first_prof['lo']),
    hi=money(first_prof['p90']),
    over=money(first_prof['p90'] - first_prof['med']),
    p1tin='{:,}'.format(first_prof['tin'] // 1_000_000),
    p1tout='{:,}'.format(first_prof['tout'] // 1_000_000),
    p1lo=money(first_prof['lo']),
    p1top=money(first_prof['p90']),
    p1med=money(first_prof['med']),
    topbill=money(prof_rows[1]['top']),
    overyr=money((first_prof['p90'] - first_prof['med']) * 12),
)
out = PAGE
for k, v in vals.items():
    out = out.replace('{{%s}}' % k, str(v))

d = os.path.join(ROOT, 'benchmark')
os.makedirs(d, exist_ok=True)
open(os.path.join(d, 'index.html'), 'w', encoding='utf-8').write(out)
print('benchmark built: %d models, %d workhorse, %d events, spread %s' % (
    len(MODELS), len(WH), len(CH), spread_words))
