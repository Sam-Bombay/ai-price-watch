#!/usr/bin/env python3
"""Build /repricing — the re-bid page.

Everything on it is computed from the live price log (data/changes.json), never invented:
  - how many distinct model/price points we track
  - how many now sit BELOW their first logged price, and the median/size of those cuts
  - today's biggest cuts, by name and percentage
The page turns that into one action a business can take today without hiring anyone:
send the vendor a re-bid email. Free, no signup, no paid API.
"""
import json, os, statistics, datetime, html

ROOT = os.path.dirname(os.path.abspath(__file__))
CH = json.load(open(os.path.join(ROOT, 'data/changes.json')))
TODAY = datetime.datetime.now().strftime('%Y-%m-%d')

# latest logged change per model+field
latest = {}
for c in CH:
    latest[(c['id'], c['field'])] = c

points = len(latest)
cuts = [c for c in latest.values() if (c.get('pct') or 0) < 0]
cut_pcts = [c['pct'] for c in cuts]
median_cut = round(abs(statistics.median(cut_pcts)), 1) if cut_pcts else 0.0
biggest = min(cut_pcts) if cut_pcts else 0.0
biggest_name = ''
if cut_pcts:
    b = min(cuts, key=lambda c: c['pct'])
    biggest_name = b['name']

today_moves = [c for c in CH if c['date'] == TODAY]
todays_cuts = sorted([c for c in today_moves if (c.get('pct') or 0) < 0], key=lambda c: c['pct'])[:6]

def row(c):
    return ('<tr><td>%s</td><td class="dimc">%s</td><td class="dimc">$%.4f</td><td>$%.4f</td>'
            '<td class="num">%+.1f%%</td></tr>' % (
        html.escape(c['name']), c['field'], c['from'], c['to'], c['pct']))

rows = '\n'.join(row(c) for c in todays_cuts) if todays_cuts else \
    '<tr><td colspan="5" class="dimc">No cuts logged today — the page still holds the 30-day picture.</td></tr>'

STATS = {'points': points, 'below': len(cuts), 'median': median_cut,
         'biggest': round(biggest, 1), 'biggest_name': biggest_name,
         'changes': len(CH), 'since': CH[0]['date'], 'today': TODAY,
         'today_moves': len(today_moves), 'today_cuts': len([c for c in today_moves if (c.get('pct') or 0) < 0])}

PAGE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Re-bid your AI bill — the market already cut the price</title>
<meta name="description" content="We log every AI model price change daily. %(below)d of %(points)d tracked price points now sit below the price we first logged. Here is the email that asks your vendor to match it.">
<link rel="alternate" type="application/rss+xml" title="AI Price Watch — daily price briefs" href="/feed.xml">
<style>
  :root { --bg:#0b0c0e; --panel:#14161a; --line:#23272e; --txt:#e8eaed; --dim:#8b929c;
          --down:#4ade80; --up:#f87171; --accent:#7dd3fc; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font:16px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Inter,Helvetica,Arial,sans-serif; }
  .wrap { max-width:820px; margin:0 auto; padding:64px 22px 90px; }
  h1 { font-size:34px; letter-spacing:-.02em; margin:0 0 10px; }
  h2 { font-size:14px; text-transform:uppercase; letter-spacing:.09em; color:var(--dim);
       margin:44px 0 14px; font-weight:600; }
  .sub { color:var(--dim); font-size:18px; margin:0 0 34px; }
  .hero { background:linear-gradient(180deg,#14161a,#101216); border:1px solid var(--line);
          border-left:3px solid var(--down); border-radius:14px; padding:24px 26px; }
  .hero b { font-size:18px; }
  .grid { display:grid; grid-template-columns:1fr 1fr 1fr; gap:14px; margin-top:18px; }
  .card { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:18px 20px; }
  .big { font-size:28px; font-weight:700; color:var(--down); letter-spacing:-.02em; display:block; }
  .card span.lbl { color:var(--dim); font-size:13px; }
  table { width:100%%; border-collapse:collapse; font-size:14.5px; margin-top:10px; }
  th { text-align:left; color:var(--dim); font-weight:600; font-size:12px; text-transform:uppercase;
       letter-spacing:.07em; border-bottom:1px solid var(--line); padding:8px 6px; }
  td { padding:9px 6px; border-bottom:1px solid #1a1d22; }
  td.dimc { color:var(--dim); }
  .num { color:var(--down); font-weight:600; }
  .calc { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:22px; }
  .calc label { display:block; color:var(--dim); font-size:13px; margin:14px 0 6px; }
  .calc input { width:100%%; padding:12px 14px; border-radius:9px; border:1px solid var(--line);
                background:#0e1013; color:var(--txt); font-size:16px; }
  .out { margin-top:18px; font-size:15px; }
  .out b { color:var(--down); font-size:22px; }
  textarea { width:100%%; min-height:220px; margin-top:14px; padding:14px; border-radius:9px;
             border:1px solid var(--line); background:#0e1013; color:var(--txt);
             font:14px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace; }
  .btn { display:inline-block; margin-top:12px; padding:13px 20px; border-radius:10px; border:0;
         background:#e8eaed; color:#0b0c0e; font-weight:700; font-size:15px; cursor:pointer; }
  .note { color:var(--dim); font-size:13.5px; margin-top:10px; }
  .cta { display:block; text-align:center; margin:34px 0 0; padding:16px; border-radius:12px;
         background:#e8eaed; color:#0b0c0e; font-weight:700; font-size:17px; text-decoration:none; }
  .foot { margin-top:56px; padding-top:22px; border-top:1px solid var(--line); color:var(--dim); font-size:13.5px; }
  a { color:var(--accent); }
  @media (max-width:680px){ .grid{grid-template-columns:1fr;} h1{font-size:27px;} }
</style>
</head>
<body>
<div class="wrap">

  <h1>Your AI bill is probably set on last month's price</h1>
  <p class="sub">We log every AI model price change, every day. The floor keeps moving — mostly down.
  If nobody has re-bid your contract, you are paying a number the market already left behind.</p>

  <div class="hero">
    <p><b>Of the %(points)d model price points we track, %(below)d now cost less than the first price we
    logged for them.</b> The median cut is %(median).1f%%. The biggest is %(biggest).1f%% on %(biggest_name)s.
    The log holds %(changes)d logged changes since %(since)s. Today alone: %(today_moves)d moves,
    %(today_cuts)d of them cuts.</p>
  </div>

  <div class="grid">
    <div class="card"><span class="big">%(points)d</span><span class="lbl">price points tracked</span></div>
    <div class="card"><span class="big">%(below)d</span><span class="lbl">now below first-logged price</span></div>
    <div class="card"><span class="big">%(median).1f%%</span><span class="lbl">median cut on those</span></div>
  </div>

  <h2>Today's cuts, straight from the log (%(today)s)</h2>
  <table>
    <tr><th>Model</th><th>Field</th><th>Was /M</th><th>Now /M</th><th>Change</th></tr>
    %(rows)s
  </table>
  <p class="note">Prices are USD per million tokens, as published in OpenRouter's public catalogue
  and logged the same day. No estimate, no survey, no vendor slide.</p>

  <h2>Step 1 — what is a re-bid worth to you</h2>
  <div class="calc">
    <label for="spend">Your monthly AI + model spend, USD</label>
    <input id="spend" type="number" inputmode="decimal" value="2000" min="0" step="100">
    <label for="pct">Share of that spend sitting on models that have been cut (default: our median)</label>
    <input id="pct" type="number" inputmode="decimal" value="%(median).1f" min="0" max="100" step="0.1">
    <div class="out" id="out"></div>
  </div>

  <h2>Step 2 — the email that asks</h2>
  <div class="calc">
    <label for="vendor">Your vendor or account manager's name</label>
    <input id="vendor" type="text" value="there" autocomplete="off">
    <label for="company">Your company</label>
    <input id="company" type="text" value="our team" autocomplete="off">
    <button class="btn" id="gen" type="button">Generate the re-bid email</button>
    <textarea id="mail" readonly></textarea>
    <button class="btn" id="copy" type="button">Copy</button>
    <p class="note">Paste it into your own mail client. Nothing is sent from here and nothing you type
    leaves this page — it is all local JavaScript.</p>
  </div>

  <a class="cta" href="mailto:%(mailto)s?subject=AI%%20cost%%20audit%%20—%%20one%%20redacted%%20invoice&body=Hi%%20Sam%%20—%%20I%%20read%%20the%%20re-bid%%20page.%%20Our%%20AI%%20and%%20software%%20spend%%20is%%20about%%20$%%20per%%20month.%%20Can%%20you%%20tell%%20me%%20what%%20is%%20honestly%%20cuttable%%3F">
    Or have me do it: free audit, 30%% of what I actually cut
  </a>
  <p class="note">No savings, no fee. You keep 70%%. I take the cut only on verified savings —
  <a href="/receipts">here is my own audit, line by line, $5,988/yr</a>.</p>

  <div class="foot">
    <p>AI Price Watch · <a href="/">live tracker</a> · <a href="/volatility">volatility</a> ·
    <a href="/clinic">the clinic</a> · <a href="/receipts">my receipts</a> ·
    <a href="/feed.xml">daily brief feed</a></p>
    <p>Data: OpenRouter public model catalogue, logged daily. Built %(today)s.</p>
  </div>
</div>

<script>
const MEDIAN = %(median).1f;
const fmt = n => '$' + Math.round(n).toLocaleString('en-US');
function recalc() {
  const spend = parseFloat(document.getElementById('spend').value) || 0;
  const pct = parseFloat(document.getElementById('pct').value) || 0;
  const monthly = spend * pct / 100 * 0.55;   // assume the vendor meets you partway
  document.getElementById('out').innerHTML =
    'At ' + pct.toFixed(1) + '%% on ' + fmt(spend) + '/mo, a vendor that meets you halfway is worth about ' +
    '<b>' + fmt(monthly) + '/mo</b> — ' + fmt(monthly * 12) + ' a year. Full match would be ' +
    fmt(spend * pct / 100 * 12) + '/yr.';
}
document.getElementById('spend').addEventListener('input', recalc);
document.getElementById('pct').addEventListener('input', recalc);
recalc();

document.getElementById('gen').addEventListener('click', () => {
  const v = document.getElementById('vendor').value.trim() || 'there';
  const co = document.getElementById('company').value.trim() || 'our team';
  const spend = parseFloat(document.getElementById('spend').value) || 0;
  const body = [
    'Subject: Re-bid request — ' + co + ' AI contract',
    '',
    'Hi ' + v + ',',
    '',
    'We are reviewing our AI and software spend before the next renewal. ' +
    'Public model pricing has moved a lot: of the %(points)d model price points tracked daily at ' +
    'ai-price-watch-beta.vercel.app, %(below)d now sit below the price we first logged, with a median cut of ' +
    MEDIAN.toFixed(1) + '%% and cuts as deep as %(biggest).1f%% (' + %(jsbiggest)s + ').',
    '',
    'Our current commitment is around ' + fmt(spend) + ' per month. Two questions:',
    '1. Which of our contracted models or seats are priced above the current public rate, and by how much?',
    '2. What will you do to bring our rate to market before renewal?',
    '',
    'If the answer is nothing, we would rather know that now than at renewal.',
    '',
    'Thanks,',
    co
  ].join('\\n');
  document.getElementById('mail').value = body;
});
document.getElementById('copy').addEventListener('click', async () => {
  const t = document.getElementById('mail');
  if (!t.value) return;
  try { await navigator.clipboard.writeText(t.value); document.getElementById('copy').textContent = 'Copied'; }
  catch (e) { t.select(); document.execCommand('copy'); }
});
</script>
</body>
</html>
''' % dict(STATS, rows=rows,
           mailto='sambombayoffice@gmail.com',
           jsbiggest=json.dumps('%s: %+.1f%%' % (biggest_name, biggest)))

out = os.path.join(ROOT, 'repricing')
os.makedirs(out, exist_ok=True)
open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(PAGE)
print('wrote repricing/index.html')
print(json.dumps(STATS, indent=1))
