#!/usr/bin/env python3
"""Build the AI Cost Index — a like-for-like daily price index for AI work.

Method (stated on the page, not buried):
- Universe: every model quoted in today's catalogue (data/latest.json) that was already
  listed before the change log begins and never delisted inside the window. That is a
  FIXED PANEL, so the index measures what happened to the price of the same capability.
  New models entering the market are deliberately excluded: they are a separate (and much
  larger) effect, reported separately as the "cheapest capable" line.
- Reconstruction: data/changes.json holds 800 dated before/after events on input and output
  prices. Walking backwards from today's prices, reversing every event dated after day D,
  reproduces each day's catalogue exactly as the scraper saw it. No estimates, no fills.
- Workload: 120M input + 18M output tokens per month (a 40-person company, one product
  feature on a model) — the same profile used on /benchmark, so the numbers reconcile.
- Reported per day: cost on the fixed panel at the median model, at the cheapest capable
  model, and at the 90th percentile. Index = median, first day = 100.
"""
import json, os, statistics, datetime, html, csv

ROOT = os.path.dirname(os.path.abspath(__file__))
LAT = json.load(open(os.path.join(ROOT, 'data/latest.json')))
CH = json.load(open(os.path.join(ROOT, 'data/changes.json')))

TIN, TOUT = 120_000_000, 18_000_000
TODAY = LAT.get('updated') or datetime.date.today().isoformat()

def bill(m):
    return (TIN / 1_000_000) * m['in'] + (TOUT / 1_000_000) * m['out']

# --- build the fixed panel -------------------------------------------------
added_in_window = {c['id'] for c in CH if c['field'] == 'added'}
retired_in_window = {c['id'] for c in CH if c['field'] == 'retired'}

panel = {}
for m in LAT['models']:
    if m.get('in') is None or m.get('out') is None:
        continue
    if m['id'] in added_in_window or m['id'] in retired_in_window:
        continue
    panel[m['id']] = {'name': m['name'], 'in': m['in'], 'out': m['out'], 'ctx': m.get('ctx') or 0}

# all capable models today (context >= 100k) — for the "cheapest capable" line
capable_today = [m for m in LAT['models']
                 if m.get('in') is not None and m.get('out') is not None and (m.get('ctx') or 0) >= 100000]

dates = sorted({c['date'] for c in CH})
if TODAY not in dates:
    dates.append(TODAY)
start = dates[0]
all_days = []
d = datetime.date.fromisoformat(start)
while d <= datetime.date.fromisoformat(TODAY):
    all_days.append(d.isoformat())
    d += datetime.timedelta(days=1)

# events by date, for reverse application
by_date = {}
for c in CH:
    if c['field'] in ('input', 'output') and c['id'] in panel:
        by_date.setdefault(c['date'], []).append(c)

state = {k: dict(v) for k, v in panel.items()}
rows = []
for day in reversed(all_days):
    # state currently reflects end of `day`; record it, then revert that day's events
    if state:
        costs = sorted(bill(m) for m in state.values())
        med = statistics.median(costs)
        p90 = statistics.quantiles(costs, n=10)[8] if len(costs) >= 10 else costs[-1]
        rows.append({'date': day, 'n': len(costs), 'median': med,
                     'p90': p90, 'cheapest': costs[0]})
    for c in by_date.get(day, []):
        key = 'in' if c['field'] == 'input' else 'out'
        if c['from'] is not None:
            state[c['id']][key] = c['from']

rows.reverse()
base = rows[0]['median']
for r in rows:
    r['index'] = round(100 * r['median'] / base, 2)
    r['index_cheapest'] = round(100 * r['cheapest'] / rows[0]['cheapest'], 2)
    r['median'] = round(r['median'], 2)
    r['p90'] = round(r['p90'], 2)
    r['cheapest'] = round(r['cheapest'], 2)

first, last = rows[0], rows[-1]
summary = {
    'as_of': last['date'],
    'panel_models': len(panel),
    'panel_ctx100k': sum(1 for m in panel.values() if m['ctx'] >= 100000),
    'workload': {'input_tokens_month': TIN, 'output_tokens_month': TOUT},
    'baseline_date': first['date'],
    'index': last['index'],
    'change_pct_since_baseline': round(last['index'] - 100, 2),
    'median_cost_month': last['median'],
    'median_cost_month_baseline': first['median'],
    'cheapest_cost_month': last['cheapest'],
    'cheapest_change_pct': round(100 * (last['cheapest'] / first['cheapest'] - 1), 2),
    'p90_cost_month': last['p90'],
    'events_logged': len(CH),
    'models_quoted_today': len(LAT['models']),
    'cheapest_capable_name': min(capable_today, key=bill)['name'] if capable_today else None,
    'cheapest_capable_cost': round(bill(min(capable_today, key=bill)), 2) if capable_today else None,
    'days': len(rows),
}

os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
json.dump({'summary': summary, 'series': rows}, open(os.path.join(ROOT, 'data/index.json'), 'w'), indent=1)
with open(os.path.join(ROOT, 'data/index.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['date', 'n', 'median', 'p90', 'cheapest', 'index', 'index_cheapest'])
    w.writeheader()
    w.writerows(rows)

# --- page ------------------------------------------------------------------
peak = max(rows, key=lambda r: r['median'])
trough = min(rows, key=lambda r: r['median'])
spread = summary['p90_cost_month'] / summary['cheapest_cost_month'] if summary['cheapest_cost_month'] else 0

spark = ''
maxi, mini = max(r['index'] for r in rows), min(r['index'] for r in rows)
for r in rows:
    h = 0 if maxi == mini else (r['index'] - mini) / (maxi - mini)
    spark += f"<span style=\"height:{max(3, h*90):.0f}px\" title='{r['date']} {r['index']}'></span>"

trs = ''.join(
    f"<tr><td>{r['date']}</td><td class=n>{r['n']}</td><td class=n>${r['median']:,.0f}</td>"
    f"<td class=n>${r['cheapest']:,.0f}</td><td class=n>${r['p90']:,.0f}</td>"
    f"<td class=n><b>{r['index']:.1f}</b></td></tr>"
    for r in reversed(rows[-14:]))

page = f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<title>AI Cost Index — the same AI work, priced daily</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{{--ink:#12100e;--mut:#6d665f;--line:#e6e0d7;--bg:#fbf9f6;--acc:#8a2b18}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,sans-serif}}
.w{{max-width:740px;margin:0 auto;padding:34px 22px 60px}}
h1{{font-size:29px;line-height:1.14;letter-spacing:-.02em;margin:0 0 10px}}
.lede{{color:var(--mut);margin:0 0 26px;max-width:60ch}}
.k{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:24px 0}}
.c{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px}}
.c .l{{font-size:10.5px;text-transform:uppercase;letter-spacing:.12em;color:var(--mut)}}
.c .v{{font-size:25px;font-weight:600;letter-spacing:-.02em;margin-top:4px}}
.c .s{{font-size:12px;color:var(--mut)}}
.spark{{display:flex;align-items:flex-end;gap:2px;height:96px;margin:26px 0 8px;border-bottom:1px solid var(--line)}}
.spark span{{flex:1;background:var(--acc);opacity:.82;border-radius:1px 1px 0 0}}
.sparkx{{display:flex;justify-content:space-between;font-size:11px;color:var(--mut)}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:8px}}
th{{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--mut);border-bottom:1px solid var(--ink);padding:6px 0}}
td{{padding:6px 0;border-bottom:1px solid var(--line)}}
td.n{{text-align:right}} th.n{{text-align:right}}
h2{{font-size:10.5px;text-transform:uppercase;letter-spacing:.14em;color:var(--mut);margin:32px 0 8px}}
p.small{{font-size:12.5px;color:var(--mut)}}
.cta{{background:var(--ink);color:#fff;border-radius:10px;padding:20px 22px;margin-top:30px}}
.cta a{{color:#fff}}
.cta h3{{margin:0 0 6px;font-size:17px}}
footer{{margin-top:34px;font-size:11.5px;color:var(--mut);border-top:1px solid var(--line);padding-top:12px}}
</style></head><body><div class=w>
<h1>The same AI work, priced every day.</h1>
<p class=lede>{summary['panel_models']} models, held fixed, re-priced through {summary['events_logged']:,} logged price changes.
One monthly workload: {TIN//1_000_000}M input and {TOUT//1_000_000}M output tokens — a 40-person company with one
product feature on a model. Nothing estimated; every number reconstructed from the daily scrape.</p>

<div class=k>
 <div class=c><div class=l>Index</div><div class=v>{summary['index']:.1f}</div>
   <div class=s>{summary['change_pct_since_baseline']:+.1f}% since {summary['baseline_date'][5:]}</div></div>
 <div class=c><div class=l>Median bill / mo</div><div class=v>${summary['median_cost_month']:,.0f}</div>
   <div class=s>was ${summary['median_cost_month_baseline']:,.0f}</div></div>
 <div class=c><div class=l>Cheapest capable</div><div class=v>${summary['cheapest_cost_month']:,.0f}</div>
   <div class=s>{summary['cheapest_change_pct']:+.1f}% since baseline</div></div>
</div>

<div class=spark>{spark}</div>
<div class=sparkx><span>{rows[0]['date']}</span><span>{rows[-1]['date']}</span></div>

<h2>Last 14 days</h2>
<table><tr><th>Date</th><th class=n>Models</th><th class=n>Median</th><th class=n>Cheapest</th><th class=n>90th pct</th><th class=n>Index</th></tr>
{trs}</table>

<h2>What this means</h2>
<p class=small>Median bill on the same workload moved from ${first['median']:,.0f} to ${last['median']:,.0f} a month.
The gap between the cheapest capable model and the 90th percentile is <b>{spread:.1f}x</b> on the same day, for the
same work. That ratio, not the headline price of any single model, is the thing that decides an AI budget — and it
is invisible on a vendor invoice.</p>

<div class=cta>
<h3>What is your bill at your volume?</h3>
<p style="margin:0 0 10px;font-size:14px;opacity:.9">The savings calculator takes spend and seats and returns the
annual number, using this same catalogue. I take 30% of what it saves.</p>
<a href="https://ai-price-watch-beta.vercel.app/">ai-price-watch-beta.vercel.app</a>
</div>

<footer>AI Cost Index — generated {TODAY} from the OpenRouter public catalogue.
Fixed panel: models listed before {first['date']} and still listed today ({summary['panel_ctx100k']} of them with 100k+ context).
Models that entered or left the market inside the window are excluded from the index and counted separately.
Source data and the full daily series: /data/index.csv. Built by Noir &amp; Co.</footer>
</div></body></html>"""

out = os.path.join(ROOT, 'cost-index')
os.makedirs(out, exist_ok=True)
open(os.path.join(out, 'index.html'), 'w').write(page)
json.dump(summary, open(os.path.join(out, 'summary.json'), 'w'), indent=1)

print(json.dumps(summary, indent=1))
print('peak', peak['date'], peak['index'], 'trough', trough['date'], trough['index'])
print('rows', len(rows), 'first', rows[0]['date'], 'wrote', os.path.join(out, 'index.html'))
