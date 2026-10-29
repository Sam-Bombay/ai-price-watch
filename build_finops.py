#!/usr/bin/env python3
"""Build /finops/ — the partner-side AI token spend assessment.

Why this exists: on 8 Oct 2026 TD SYNNEX launched FinOps Fusion so its MSP partners can sell
"AI cost management" as a recurring service, and it told the channel the assessment that
establishes a token baseline ships "later this year" (Business Wire, 8 Oct; ChannelE2E 29 Oct).
An MSP that has bought the idea still needs the artefact it hands the client's CFO. This is
that artefact, free, no login, no upload.

Every price is read from today's OpenRouter catalogue (data/latest.json). All arithmetic is done
in Python here to sanity-check, and in the page from the same embedded table, so an MSP can
re-run every number. The demo volumes are labelled fictional.
"""
import json, os, datetime, statistics, html

ROOT = os.path.dirname(os.path.abspath(__file__))
LATEST = json.load(open(os.path.join(ROOT, 'data/latest.json')))
TODAY = datetime.date.today().isoformat()
SRC_DATE = LATEST.get('updated', TODAY)

models = []
for m in LATEST['models']:
    i, o = m.get('in'), m.get('out')
    if i is None or o is None or i <= 0 or o <= 0:
        continue
    models.append({'id': m['id'], 'n': m.get('name') or m['id'],
                   'i': i, 'o': o, 'c': m.get('ctx') or 0})
models.sort(key=lambda m: m['i'] + m['o'])

# demo workload — clearly fictional, three lines, cents-to-hundreds spread
DEMO = [
    ('qwen/qwen3.5-122b-a10b', 180.0, 24.0),
    ('~z-ai/glm-latest', 60.0, 9.0),
    ('moonshotai/kimi-k3', 12.0, 3.0),
]
by_id = {m['id']: m for m in models}

def cost(m, ti, to):
    return ti * m['i'] + to * m['o']

demo_now = sum(cost(by_id[i], ti, to) for i, ti, to in DEMO if i in by_id)
demo_ti = sum(t for _, t, _ in DEMO)
demo_to = sum(t for _, _, t in DEMO)

# cheapest model that can hold the largest context the workload uses, and the p50/p90 of the
# whole qualifying market for the SAME token mix — the spread is the sales argument
need_ctx = max((by_id[i]['c'] for i, _, _ in DEMO if i in by_id), default=128000)
qual = [m for m in models if m['c'] >= need_ctx]
mix = [cost(m, demo_ti, demo_to) for m in qual]
cheapest = min(qual, key=lambda m: cost(m, demo_ti, demo_to))
p50 = statistics.median(mix)
p90 = sorted(mix)[int(len(mix) * 0.9)]

payload = json.dumps(models, separators=(',', ':'))

def money(v):
    return f"${v:,.2f}"

PAGE = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI token spend assessment — what a client's workload should cost</title>
<meta name="description" content="Enter a client's monthly token volumes, get the current bill, the cheapest capable swap and the annual saving. Prices from the live OpenRouter catalogue, rebuilt daily.">
<style>
:root{{--ink:#12100e;--mut:#6b6560;--line:#e2ddd6;--bg:#fbf9f6;--acc:#1a5c3a;--warn:#8a3b12}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}
.wrap{{max-width:900px;margin:0 auto;padding:40px 20px 80px}}
h1{{font-size:30px;line-height:1.15;margin:0 0 10px;letter-spacing:-.02em}}
h2{{font-size:19px;margin:34px 0 10px;letter-spacing:-.01em}}
p.lede{{color:var(--mut);margin:0 0 22px;max-width:62ch}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
th,td{{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);font-weight:600}}
input,select{{font:inherit;font-size:14px;padding:7px 8px;border:1px solid var(--line);border-radius:6px;background:#fff;width:100%}}
input[type=number]{{text-align:right}}
button{{font:inherit;font-size:14px;padding:9px 16px;border-radius:6px;border:1px solid var(--ink);background:var(--ink);color:#fff;cursor:pointer}}
button.ghost{{background:#fff;color:var(--ink)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}}
.card{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.card .k{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)}}
.card .v{{font-size:24px;font-weight:650;letter-spacing:-.02em;margin-top:4px}}
.card .s{{font-size:12px;color:var(--mut);margin-top:2px}}
.good .v{{color:var(--acc)}}
.note{{font-size:13px;color:var(--mut);border-left:2px solid var(--line);padding-left:12px;margin:16px 0}}
.foot{{font-size:12px;color:var(--mut);margin-top:40px;border-top:1px solid var(--line);padding-top:14px}}
a{{color:var(--acc)}}
.row rm{{cursor:pointer;color:var(--mut);font-size:12px}}
@media print{{body{{background:#fff}}.noprint{{display:none}}}}
</style></head><body><div class="wrap">

<h1>The token spend assessment</h1>
<p class="lede">An MSP now sells "AI cost management" as a recurring line. This is the page that
produces the number the client's CFO signs. Put in the monthly token volumes, get what the
workload costs today, what the cheapest capable model would cost, and the annual difference.
No login, nothing uploaded, every price dated.</p>

<h2>1. The client's workload</h2>
<table><thead><tr>
<th style="width:52%">Model</th><th style="width:16%">M tokens in /mo</th><th style="width:16%">M tokens out /mo</th><th style="width:16%"></th>
</tr></thead><tbody id="rows"></tbody></table>
<p class="noprint" style="margin-top:12px">
<button class="ghost" onclick="addRow()">Add a line</button>
<button onclick="calc()">Work it out</button></p>

<div class="grid" id="out"></div>

<h2>2. What that says to the buyer</h2>
<div id="verdict" class="note"></div>

<h2>3. How the number is produced</h2>
<p class="lede" style="font-size:14px">Cost = (millions of input tokens × input price) +
(millions of output tokens × output price), with both prices per million tokens, read from the
OpenRouter catalogue of {len(models)} listed models on {SRC_DATE}. The comparison set is every
model that can hold the context size in use ({need_ctx:,} tokens). No savings are assumed
beyond a like-for-like swap on published prices; nothing here accounts for quality differences,
eval results or migration cost, which is the review a human does afterwards.</p>

<div class="foot">
Prices: OpenRouter public catalogue, snapshot {SRC_DATE}, rebuilt daily by ai-price-watch.
The three demo lines are a fictional workload, not a client. A working review of one real
account is available — see <a href="/msp">/msp</a> and <a href="/repricing">/repricing</a>.
</div>

<script>
const MODELS = {payload};
const byId = Object.fromEntries(MODELS.map(m=>[m.id,m]));
const DEMO = {json.dumps(DEMO)};
function money(v){{return '$'+v.toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}})}}
function addRow(id, ti, to){{
  const tb=document.getElementById('rows');
  const tr=document.createElement('tr');
  tr.innerHTML='<td><input list="models" value="'+(id||'')+'" class="mid" placeholder="model id"></td>'
   +'<td><input type="number" class="tin" min="0" step="1" value="'+(ti??'')+'"></td>'
   +'<td><input type="number" class="tout" min="0" step="1" value="'+(to??'')+'"></td>'
   +'<td class="noprint"><span class="row" onclick="this.closest(&quot;tr&quot;).remove()">remove</span></td>';
  tb.appendChild(tr);
}}
function calc(){{
  const rows=[...document.querySelectorAll('#rows tr')];
  let now=0, tin=0, tout=0, need=0, bad=[];
  rows.forEach(r=>{{
    const id=r.querySelector('.mid').value.trim();
    const ti=parseFloat(r.querySelector('.tin').value)||0;
    const to=parseFloat(r.querySelector('.tout').value)||0;
    const m=byId[id];
    if(!m){{ if(id) bad.push(id); return; }}
    now+=ti*m.i+to*m.o; tin+=ti; tout+=to; need=Math.max(need,m.c||0);
  }});
  const qual=MODELS.filter(m=>(m.c||0)>=need);
  const c=m=>tin*m.i+tout*m.o;
  const costs=qual.map(c).sort((a,b)=>a-b);
  const best=qual.reduce((a,b)=>c(a)<=c(b)?a:b);
  const bestCost=c(best);
  const p50=costs.length?costs[Math.floor(costs.length/2)]:0;
  const p90=costs.length?costs[Math.floor(costs.length*0.9)]:0;
  const save=Math.max(0,now-bestCost), yr=save*12;
  const share=yr*0.3;
  document.getElementById('out').innerHTML=
   '<div class="card"><div class="k">Bill today</div><div class="v">'+money(now)+'</div><div class="s">per month at list prices</div></div>'
  +'<div class="card good"><div class="k">Cheapest capable</div><div class="v">'+money(bestCost)+'</div><div class="s">'+best.n+'</div></div>'
  +'<div class="card good"><div class="k">Annual difference</div><div class="v">'+money(yr)+'</div><div class="s">'+money(save)+' per month</div></div>'
  +'<div class="card"><div class="k">Market median / p90</div><div class="v">'+money(p50)+' / '+money(p90)+'</div><div class="s">'+qual.length+' qualifying models</div></div>';
  const v=document.getElementById('verdict');
  if(bad.length){{ v.textContent='Not in today\\'s catalogue: '+bad.join(', ')+'. Check the model id.'; return; }}
  if(now<=0){{ v.textContent='Enter volumes above.'; return; }}
  const ratio=(now/Math.max(bestCost,0.000001));
  v.innerHTML='This workload bills '+money(now)+' a month and the same token mix is available at '
   +money(bestCost)+' — '+ratio.toFixed(1)+'x cheaper, '+money(yr)+' a year. Across the '
   +qual.length+' models that can hold '+need.toLocaleString()+' tokens the median is '+money(p50)
   +' and the ninetieth percentile '+money(p90)+', so the client is '+(now>p50?'above':'below')
   +' the market middle. On a 30% share of verified net savings that is '
   +money(share)+' a year to whoever runs the review.';
}}
MODELS.forEach(()=>{{}});
document.addEventListener('DOMContentLoaded',()=>{{
  const dl=document.createElement('datalist'); dl.id='models';
  MODELS.forEach(m=>{{const o=document.createElement('option');o.value=m.id;o.label=m.n+' — $'+m.i+'/in $'+m.o+'/out';dl.appendChild(o)}});
  document.body.appendChild(dl);
  DEMO.forEach(d=>addRow(d[0],d[1],d[2]));
  addRow();
  calc();
}});
</script></div></body></html>
"""

os.makedirs(os.path.join(ROOT, 'finops'), exist_ok=True)
open(os.path.join(ROOT, 'finops/index.html'), 'w').write(PAGE)

print(f"models={len(models)} source={SRC_DATE}")
print(f"demo: today={money(demo_now)} cheapest={money(cost(cheapest, demo_ti, demo_to))} ({cheapest['n']})")
print(f"demo: median={money(p50)} p90={money(p90)} qualifying={len(qual)} ctx>={need_ctx}")
print(f"demo: annual saving={money((demo_now-cost(cheapest, demo_ti, demo_to))*12)}")
print("wrote finops/index.html", os.path.getsize(os.path.join(ROOT, 'finops/index.html')), "bytes")
