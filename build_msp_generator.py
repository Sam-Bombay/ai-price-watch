#!/usr/bin/env python3
"""Build /msp/generator/ — the white-label client report an MSP hands to its own client.

Why: /finops computes a number for whoever is looking at the screen; /msp explains the offer.
What was missing is the artefact that leaves the building: a report with the MSP's name on it,
a dated price trail behind every line, and a print/PDF path. An MSP can open this in front of a
client, type four fields, and hand over a document the same minute. No login, nothing uploaded,
all arithmetic in the page so the client can re-run it.

Every price comes from today's OpenRouter catalogue (data/latest.json). The evidence lines come
from the logged change file (data/changes.json), so they are dated observations, not claims.
"""
import json, os, datetime, statistics

ROOT = os.path.dirname(os.path.abspath(__file__))
LATEST = json.load(open(os.path.join(ROOT, 'data/latest.json')))
CHANGES = json.load(open(os.path.join(ROOT, 'data/changes.json')))
TODAY = datetime.date.today().isoformat()
SRC_DATE = LATEST.get('updated', TODAY)

models = []
for m in LATEST['models']:
    i, o = m.get('in'), m.get('out')
    if i is None or o is None or i <= 0 or o <= 0:
        continue
    models.append({'id': m['id'], 'n': (m.get('name') or m['id']).replace('\u2014', '-'),
                   'i': i, 'o': o, 'c': m.get('ctx') or 0})
models.sort(key=lambda m: m['i'] + m['o'])

# reference mix used only to rank the market: 3 input tokens per output token
TIN, TOUT = 120.0, 40.0  # millions/month, a 40-person company shaped like the /benchmark demo
need_ctx = 128000
qual = [m for m in models if m['c'] >= need_ctx]
cost = lambda m: TIN * m['i'] + TOUT * m['o']
ranked = sorted(qual, key=cost)
cheapest = ranked[0]
mix = [cost(m) for m in qual]
median = statistics.median(mix)
p90 = sorted(mix)[int(len(mix) * 0.9)]

# today's dated evidence: the largest absolute moves logged today
today_moves = [c for c in CHANGES if c.get('date') == TODAY and c.get('pct') is not None]
today_moves.sort(key=lambda c: -abs(c['pct']))
evidence = []
seen = set()
for c in today_moves:
    if c['name'] in seen or c.get('field') not in ('input', 'output'):
        continue
    seen.add(c['name'])
    evidence.append({'d': c['date'], 'n': c['name'], 'f': c['field'],
                     'a': c.get('from'), 'b': c.get('to'), 'p': c.get('pct')})
    if len(evidence) == 4:
        break

moves_today = len({(c['name'], c['field']) for c in CHANGES if c.get('date') == TODAY})
total_logged = len(CHANGES)

payload = json.dumps(models, separators=(',', ':'))
ev_json = json.dumps(evidence, separators=(',', ':'))

def money(v):
    return f"${v:,.2f}"

PAGE = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Client AI cost review — white-label report generator</title>
<meta name="description" content="Type the client's monthly AI spend, get a dated, print-ready cost review with your MSP's name on it. Prices from {len(models)} listed models, rebuilt daily. Nothing uploaded.">
<style>
:root{{--ink:#111315;--mut:#6a7077;--line:#e3e6ea;--bg:#f7f8f9;--acc:#14532d;--acc2:#166534;--warn:#9a3412}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}
.wrap{{max-width:940px;margin:0 auto;padding:36px 18px 90px}}
h1{{font-size:29px;line-height:1.15;margin:0 0 8px;letter-spacing:-.02em}}
h2{{font-size:18px;margin:30px 0 10px}}
p.lede{{color:var(--mut);margin:0 0 20px;max-width:64ch;font-size:15px}}
.sheet{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:22px 22px 26px;margin-top:18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}
label{{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin:0 0 5px;font-weight:600}}
input,select{{font:inherit;font-size:14px;padding:8px 9px;border:1px solid var(--line);border-radius:6px;background:#fff;width:100%}}
input[type=number]{{text-align:right}}
button{{font:inherit;font-size:14px;padding:10px 16px;border-radius:6px;border:1px solid var(--ink);background:var(--ink);color:#fff;cursor:pointer}}
button.ghost{{background:#fff;color:var(--ink)}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:16px 0 6px}}
.kpi{{border:1px solid var(--line);border-radius:10px;padding:13px 15px}}
.kpi .k{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);font-weight:600}}
.kpi .v{{font-size:24px;font-weight:680;letter-spacing:-.02em;margin-top:3px}}
.kpi .s{{font-size:12px;color:var(--mut);margin-top:2px}}
.good .v{{color:var(--acc2)}}
table{{width:100%;border-collapse:collapse;font-size:14px;margin-top:8px}}
th,td{{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);font-weight:600}}
td.n,th.n{{text-align:right;font-variant-numeric:tabular-nums}}
.note{{font-size:13px;color:var(--mut);border-left:2px solid var(--line);padding-left:12px;margin:16px 0}}
.hdr{{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;border-bottom:2px solid var(--ink);padding-bottom:12px;margin-bottom:16px}}
.hdr .who{{font-size:13px;color:var(--mut);text-align:right}}
.foot{{font-size:12px;color:var(--mut);margin-top:34px;border-top:1px solid var(--line);padding-top:12px}}
a{{color:var(--acc2)}}
.flag{{background:#fff7ed;border:1px solid #fed7aa;color:var(--warn);border-radius:8px;padding:10px 12px;font-size:13px;margin:14px 0}}
@media print{{
 body{{background:#fff}} .noprint{{display:none!important}} .wrap{{padding:0;max-width:none}}
 .sheet{{border:0;padding:0;margin:0;border-radius:0}} h1{{display:none}}
 .printonly{{display:block}}
}}
.printonly{{display:none}}
</style></head><body><div class="wrap">

<h1>Client AI cost review — generate it, hand it over</h1>
<p class="lede">Four fields in, one dated document out, with your firm's name at the top and a
print-to-PDF button. This is the deliverable an MSP can put in front of a client without
booking anything: what the AI bill is, what the same work costs at today's cheapest capable
price, and the dated trail behind the claim. Nothing is uploaded; the arithmetic runs in this page
from {len(models)} listed models.</p>

<div class="grid noprint">
  <div><label>Your firm (MSP)</label><input id="mspName" value="Your firm name" placeholder="Northgate IT"></div>
  <div><label>Client name</label><input id="clientName" value="Client name" placeholder="Acme Manufacturing"></div>
  <div><label>Client monthly AI / API spend (USD)</label><input id="spend" type="number" min="0" step="50" value="2000"></div>
  <div><label>What they pay today (model)</label><select id="curModel"></select></div>
  <div><label>Seats (optional)</label><input id="seats" type="number" min="0" step="1" value="40"></div>
</div>
<p class="noprint" style="margin-top:14px">
  <button onclick="render()">Build the review</button>
  <button class="ghost" onclick="window.print()">Print / save PDF</button>
</p>

<div class="sheet" id="sheet">
  <div class="hdr">
    <div><div style="font-size:11px;text-transform:uppercase;letter-spacing:.1em;color:#6a7077">AI &amp; software cost review</div>
      <div style="font-size:22px;font-weight:680;letter-spacing:-.02em" id="rMsp">Your firm name</div></div>
    <div class="who"><div id="rDate"></div><div>Prepared for <strong id="rClient">Client name</strong></div></div>
  </div>

  <div class="kpis" id="kpis"></div>
  <p id="verdict" class="note"></p>
  <div id="flag" class="flag" style="display:none"></div>

  <h2>Where the money is</h2>
  <table><thead><tr><th>Line</th><th class="n">Monthly</th><th class="n">Annual</th><th>Basis</th></tr></thead>
  <tbody id="lines"></tbody></table>

  <h2>Prices that moved today ({moves_today} logged events, {total_logged:,} in the log)</h2>
  <table><thead><tr><th>Model</th><th>Field</th><th class="n">Was</th><th class="n">Now</th><th class="n">Change</th></tr></thead>
  <tbody id="evidence"></tbody></table>
  <p class="note">A bill set on last quarter's rate card is wrong in both directions. The point of
  the review is not that AI got cheaper or dearer — it is that the price your client is paying was
  chosen on a day that has passed.</p>

  <h2>What happens next</h2>
  <ol style="font-size:14px;color:#111315;padding-left:20px;max-width:70ch">
    <li>Pull one month of the client's real usage (provider portal export, no credentials needed).</li>
    <li>Re-cost that exact token mix at today's prices — not a demonstration workload.</li>
    <li>Test the top swap on a sample of real prompts before anything is moved.</li>
    <li>Only then quote. A saving is verified net of migration effort, not gross of a rate-card difference.</li>
  </ol>

  <div class="foot">
    Prices: OpenRouter public catalogue, snapshot {SRC_DATE}, {len(models)} models with both prices.
    Comparison set: models holding at least 128,000 tokens of context ({len(qual)} at snapshot).
    This report is a market-price comparison, not an audit of the client's contract: committed
    discounts, enterprise agreements and credit deals are not visible in list prices. Generated
    {TODAY} by the free tool at /msp/generator — no data left the browser.
  </div>
</div>

<h2 class="noprint">If the client wants it done for them</h2>
<p class="lede noprint">The generator proves the gap on list prices. The paid work is the part it
cannot do: reading the actual invoice, the committed discount, the seat sprawl and the switching
cost, then verifying the saving after the change. Fixed price, one redacted export, no access to
systems: <a href="/msp">/msp</a> for the offer, <a href="/finops">/finops</a> for the token-level
worksheet, <a href="/benchmark">/benchmark</a> for the market spread.</p>

<script>
const MODELS = {payload};
const EVIDENCE = {ev_json};
const SRC_DATE = {json.dumps(SRC_DATE)};

function money(v){{ return '$' + v.toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}}); }}
function pct(v){{ return (v>0?'+':'') + v.toFixed(1) + '%'; }}

// pure function: every number on the page comes from here.
// A like-for-like comparison only. The client's model sits in a price class (frontier / mid /
// light, by blended cost), and the comparison set is the same class at the same context floor.
// Comparing a frontier model against a 2-cent model produces a 100x "saving" that would be a lie
// in a client meeting; that is the routing upside, and it is shown separately as the ceiling.
function computeReport(inp, models){{
  const spend = Math.max(0, Number(inp.spend)||0);
  const seats = Math.max(0, Number(inp.seats)||0);
  const MINCTX = 128000;
  const blended = (m) => 0.75*m.i + 0.25*m.o;
  const tierOf = (b) => b >= 8 ? 2 : (b >= 1 ? 1 : 0);          // frontier / mid / light
  const cur = models.find(m=>m.id===inp.curModel) || models[0];
  const tier = tierOf(blended(cur));
  const inClass = models.filter(m => (m.c||0) >= MINCTX && tierOf(blended(m)) === tier);
  const all = models.filter(m => (m.c||0) >= MINCTX);
  // implied monthly token volume: the client's dollars at their own model's blended rate
  const volume = blended(cur) > 0 ? spend / blended(cur) : 0;   // millions of tokens /mo
  const tin = volume*0.75, tout = volume*0.25;
  const costOf = (m) => tin*m.i + tout*m.o;
  const ranked = inClass.map(m=>({{m, c: costOf(m)}})).sort((a,b)=>a.c-b.c);
  const allRanked = all.map(m=>({{m, c: costOf(m)}})).sort((a,b)=>a.c-b.c);
  const best = ranked[0] || {{m: cur, c: spend}};
  const mid = ranked[Math.floor(ranked.length/2)] || best;
  const floorAll = allRanked[0] || best;
  const fair = Math.min(spend, mid.c);          // class middle = the conservative claim
  const floor = Math.min(fair, best.c);         // class floor  = the ceiling
  const save = Math.max(0, spend - fair);
  return {{
    spend, seats, cur, best: best.m, bestAll: floorAll.m,
    tier, classN: ranked.length,
    floor, fair, median: mid.c, ceiling: floorAll.c,
    volume, tin, tout,
    saveMo: save, saveYr: save*12,
    ceilingMo: Math.max(0, spend - floorAll.c), ceilingYr: Math.max(0, spend - floorAll.c)*12,
    ratio: fair > 0 ? spend/fair : 0,
    ratioAll: floorAll.c > 0 ? spend/floorAll.c : 0,
    atFloor: spend <= fair*1.02,
    tierName: ['light','mid','frontier'][tier]
  }};
}}

function fillSelect(){{
  const sel = document.getElementById('curModel');
  const prefer = ['anthropic/claude-sonnet-4.5','openai/gpt-5.2','openai/gpt-5-mini','google/gemini-2.5-pro'];
  let def = null;
  for (const p of prefer) {{ const hit = MODELS.find(m=>m.id===p); if (hit) {{ def = hit; break; }} }}
  MODELS.slice().sort((a,b)=>(b.i+b.o)-(a.i+a.o)).forEach(m=>{{
    const o=document.createElement('option'); o.value=m.id;
    o.textContent=m.n+' — $'+m.i+' in / $'+m.o+' out';
    sel.appendChild(o);
  }});
  sel.value = (def||MODELS[0]).id;
}}

function render(){{
  const inp = {{
    spend: document.getElementById('spend').value,
    seats: document.getElementById('seats').value,
    curModel: document.getElementById('curModel').value
  }};
  const r = computeReport(inp, MODELS);
  const msp = document.getElementById('mspName').value.trim() || 'Your firm name';
  const client = document.getElementById('clientName').value.trim() || 'Client name';
  document.getElementById('rMsp').textContent = msp;
  document.getElementById('rClient').textContent = client;
  document.getElementById('rDate').textContent = new Date().toLocaleDateString('en-US',{{year:'numeric',month:'long',day:'numeric'}});

  document.getElementById('kpis').innerHTML =
    '<div class="kpi"><div class="k">AI bill today</div><div class="v">'+money(r.spend)+'</div><div class="s">per month, '+r.cur.n+'</div></div>'
    +'<div class="kpi good"><div class="k">Class middle, same volume</div><div class="v">'+money(r.fair)+'</div><div class="s">'+r.classN+' comparable '+r.tierName+' models</div></div>'
    +'<div class="kpi good"><div class="k">Annual gap</div><div class="v">'+money(r.saveYr)+'</div><div class="s">'+money(r.saveMo)+' a month, before effort</div></div>'
    +'<div class="kpi"><div class="k">Ceiling if re-routed</div><div class="v">'+money(r.ceilingYr)+'</div><div class="s">cheapest anywhere: '+r.bestAll.n+'</div></div>';

  document.getElementById('verdict').innerHTML = r.atFloor
    ? 'On today\\'s list prices this client already sits at the middle of its own price class: '+money(r.spend)+' a month, against '+money(r.fair)+' for the same volume at the class middle. That is the finding and it is worth saying out loud, because the next question is not the rate card — it is the contract, the seats and the tools nobody uses. None of those are visible in list prices.'
    : 'This client bills '+money(r.spend)+' a month for a '+r.tierName+'-class model. The same token volume at the middle of that same class is '+money(r.fair)+' a month, worth '+money(r.saveYr)+' a year at list prices before any migration effort. Going below the class — routing the simple traffic to a small model — is a further '+money(r.ceilingYr)+' a year ceiling, but that one only counts after the prompts have been tested on the cheaper model, so it is not in the headline.';

  const fl = document.getElementById('flag');
  if (r.saveYr < 1200) {{
    fl.style.display='block';
    fl.textContent='Honest read: at this volume the like-for-like list-price gap is under $1,200 a year. That is not worth moving a client for. The review earns its fee on seat sprawl, unused tools and committed-discount mismatch, not on the rate card — and where the gap is this small, the right advice is to leave it alone.';
  }} else {{ fl.style.display='none'; }}

  const seatCost = r.seats>0 ? r.spend/r.seats : 0;
  document.getElementById('lines').innerHTML =
    '<tr><td>Current rate card</td><td class="n">'+money(r.spend)+'</td><td class="n">'+money(r.spend*12)+'</td><td>'+r.cur.n+', list price</td></tr>'
    +'<tr><td>Same class, class middle</td><td class="n">'+money(r.fair)+'</td><td class="n">'+money(r.fair*12)+'</td><td>'+r.classN+' comparable models</td></tr>'
    +'<tr><td><strong>Gap at list prices</strong></td><td class="n"><strong>'+money(r.saveMo)+'</strong></td><td class="n"><strong>'+money(r.saveYr)+'</strong></td><td>before migration effort</td></tr>'
    +(r.ceilingYr>r.saveYr?'<tr><td>Route simple traffic down a class</td><td class="n">'+money(r.ceilingMo-r.saveMo)+'</td><td class="n">'+money(r.ceilingYr-r.saveYr)+'</td><td>needs prompt tests first</td></tr>':'')
    +(r.seats>0?'<tr><td>Per seat, today</td><td class="n">'+money(seatCost)+'</td><td class="n">'+money(seatCost*12)+'</td><td>'+r.seats+' seats</td></tr>':'');

  document.getElementById('evidence').innerHTML = EVIDENCE.map(e=>
    '<tr><td>'+e.n+'</td><td>'+e.f+'</td><td class="n">$'+Number(e.a).toFixed(4)+'</td><td class="n">$'+Number(e.b).toFixed(4)+'</td><td class="n" style="color:'+(e.p<0?'#166534':'#9a3412')+'">'+pct(e.p)+'</td></tr>'
  ).join('') || '<tr><td colspan="5">No changes logged today.</td></tr>';
}}

document.addEventListener('DOMContentLoaded', ()=>{{ fillSelect(); render(); }});
</script></div></body></html>
"""

outdir = os.path.join(ROOT, 'msp', 'generator')
os.makedirs(outdir, exist_ok=True)
open(os.path.join(outdir, 'index.html'), 'w').write(PAGE)

# --- Python mirror of computeReport, so the page's arithmetic is checked against a second
# implementation before it ships (see verify_generator.py)
def report(spend, cur_id, seats=0):
    blended_of = lambda m: 0.75 * m['i'] + 0.25 * m['o']
    tier_of = lambda b: 2 if b >= 8 else (1 if b >= 1 else 0)
    cur = next((m for m in models if m['id'] == cur_id), models[0])
    tier = tier_of(blended_of(cur))
    volume = spend / blended_of(cur) if blended_of(cur) > 0 else 0
    tin, tout = volume * 0.75, volume * 0.25
    q = [m for m in models if (m['c'] or 0) >= 128000]
    in_class = sorted(((m, tin * m['i'] + tout * m['o']) for m in q
                       if tier_of(blended_of(m)) == tier), key=lambda x: x[1])
    allq = sorted(((m, tin * m['i'] + tout * m['o']) for m in q), key=lambda x: x[1])
    best, floor = in_class[0]
    median = in_class[len(in_class) // 2][1]
    fair = min(spend, median)
    save = max(0.0, spend - fair)
    ceiling = max(0.0, spend - allq[0][1])
    return {'floor': floor, 'fair': fair, 'median': median, 'best': best['n'],
            'saveYr': save * 12, 'ceilingYr': ceiling * 12,
            'ratio': spend / fair if fair > 0 else 0}

print(f"models={len(models)} source={SRC_DATE} qualifying={len(qual)} moves_today={moves_today} logged={total_logged}")
print(f"market ref mix ({TIN:.0f}M in / {TOUT:.0f}M out): cheapest={money(cost(cheapest))} ({cheapest['n']}), median={money(median)}, p90={money(p90)}")
print(f"evidence: {[(e['n'], e['p']) for e in evidence]}")
demo = report(2000, "openai/gpt-5.2", 40)
print(f"demo $2,000/mo on gpt-5.2: class middle={money(demo['fair'])} annual gap={money(demo['saveYr'])} ceiling={money(demo['ceilingYr'])}")
print("wrote msp/generator/index.html", os.path.getsize(os.path.join(outdir, 'index.html')), "bytes")
