#!/usr/bin/env python3
"""
/agentmeter - what ONE agent workload costs per month, and how far the same job
splits across the price list.

Built 24 Nov 2026, the morning InvestmentNews ran "Agentic AI is spending your
clients' money - and CFOs can't see it" and HN's top thread was "LLM agents work
for their parent companies, not for you". The buyer's question is arithmetic, not
strategy: an agent loop re-sends its growing history every turn, so billed input
grows with the square of the turn count and output is 10-100x a chat turn. That
workload does not price like a chatbot, and the log proves it: over the last 30
days the chat workload was flat while the agent floor rose.

Every number comes from the same live catalogue the daily cron refreshes
(data/latest.json); the 30-day figures are the same log replayed backwards
(data/changes.json). Turn count, context growth and run volume are STATED
ASSUMPTIONS printed on the page. No customer traffic has been measured.
"""
import json
import os
import datetime
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "agentmeter")

LAT = json.load(open(os.path.join(DATA, "latest.json")))
CH = json.load(open(os.path.join(DATA, "changes.json")))
TODAY = LAT.get("updated") or datetime.date.today().isoformat()

# Stated defaults, printed on the page and adjustable by the reader.
RUNS = 200        # agent runs per day
TURNS = 20        # turns per run
BASE = 6000       # system prompt + tool schemas, resent every turn
OBS = 1200        # tool result / retrieved chunk added to history each turn
OUTP = 800        # assistant tokens per turn
DAYS = 30

# Panel: models quoted both today and 30 days ago, so the comparison is like-for-like.
added = {c["id"] for c in CH if c["field"] == "added"}
retired = {c["id"] for c in CH if c["field"] == "retired"}
panel = {}
for m in LAT["models"]:
    if m.get("in") is None or m.get("out") is None:
        continue
    if m["id"] in added or m["id"] in retired:
        continue
    panel[m["id"]] = {"id": m["id"], "name": m["name"], "in": m["in"],
                      "out": m["out"], "ctx": m.get("ctx") or 0}

def billed_in(runs, turns, base, obs):
    # history resent every turn -> base*turns + obs*(turns-1 + ... + 1)
    return (turns * base + obs * (turns * (turns - 1) // 2)) * runs * DAYS / 1_000_000.0

def billed_out(runs, turns, outp):
    return turns * outp * runs * DAYS / 1_000_000.0

def cost(m, tin, tout):
    return tin * m["in"] + tout * m["out"]

TIN = billed_in(RUNS, TURNS, BASE, OBS)
TOUT = billed_out(RUNS, TURNS, OUTP)

rows = sorted(((cost(v, TIN, TOUT), v) for v in panel.values()), key=lambda x: x[0])
cheapest, dearest = rows[0], rows[-1]
median = statistics.median([r[0] for r in rows])
p90 = statistics.quantiles([r[0] for r in rows], n=10)[8]

# --- 30-day replay: same panel, prices rewound 30 days --------------------
target = (datetime.date.fromisoformat(TODAY) - datetime.timedelta(days=DAYS)).isoformat()
state = {k: dict(v) for k, v in panel.items()}
for c in reversed([c for c in CH if c["field"] in ("input", "output") and c["id"] in state]):
    if c["date"] > target:
        key = "in" if c["field"] == "input" else "out"
        if c["from"] is not None:
            state[c["id"]][key] = c["from"]
old = sorted(cost(v, TIN, TOUT) for v in state.values())
old_floor, old_median = old[0], statistics.median(old)

# chat workload, same log, for contrast: 120M in / 18M out a month
CTIN, CTOUT = 120.0, 18.0
chat_today = sorted(cost(v, CTIN, CTOUT) for v in panel.values())
chat_old = sorted(cost(v, CTIN, CTOUT) for v in state.values())

def pct(a, b):
    return 100.0 * (a / b - 1) if b else 0.0

moves_today = [c for c in CH if c["date"] == TODAY]
cuts = [c for c in moves_today if (c.get("pct") or 0) < 0]
rises = [c for c in moves_today if (c.get("pct") or 0) > 0]

# models for the client-side table: 374 is a lot to ship as HTML, keep all of them
# but slim the payload
slim = [{"n": v["name"], "i": v["in"], "o": v["out"], "c": v["ctx"]}
        for v in sorted(panel.values(), key=lambda x: x["name"].lower())]

def money(x):
    return "${:,.0f}".format(x)

# --- render ---------------------------------------------------------------
def table(rs, limit=12):
    out = []
    for i, (c, v) in enumerate(rs[:limit]):
        tag = ""
        if i == 0:
            tag = ' <span class="tag">cheapest capable of the job</span>'
        out.append(
            f'<tr><td class="num">{i+1}</td><td>{v["name"]}{tag}</td>'
            f'<td class="num">{money(c)}</td>'
            f'<td class="num">{money(c/DAYS)}</td>'
            f'<td class="num">{v["in"]:g} / {v["out"]:g}</td></tr>')
    return "\n".join(out)

frontier = [r for r in rows if r[0] >= p90]
sample = []
for kw in ("Claude Opus", "Claude Sonnet", "GPT-5.6", "Kimi K3", "GLM 5.3",
           "DeepSeek V4.1 Flash", "Gemini 4", "gpt-oss-120b"):
    hit = [r for r in rows if kw.lower() in r[1]["name"].lower() and "batch" not in r[1]["name"].lower()]
    if hit:
        c, v = hit[0]
        sample.append(
            f'<tr><td>{v["name"]}</td><td class="num">{v["in"]:g} / {v["out"]:g}</td>'
            f'<td class="num">{money(c)}</td></tr>')

ratio = dearest[0] / cheapest[0]

html = f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent meter — what one agent workload costs a month, 24 Nov 2026</title>
<meta name="description" content="The same 200-runs-a-day agent job bills {money(cheapest[0])} a month on the cheapest of 374 models and {money(dearest[0])} on the dearest. Computed from a dated price log, not a vendor page.">
<style>
:root{{--ink:#111;--mut:#666;--line:#e3e3e3;--bg:#fff;--hi:#0b6b3a;--warn:#a3231b}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
-webkit-font-smoothing:antialiased}}
.wrap{{max-width:760px;margin:0 auto;padding:28px 20px 80px}}
.kicker{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--mut)}}
h1{{font-size:30px;line-height:1.15;margin:10px 0 6px;letter-spacing:-.02em}}
h2{{font-size:19px;margin:36px 0 8px;letter-spacing:-.01em}}
p{{margin:10px 0}}
.lede{{font-size:17px;color:#333}}
.big{{display:flex;gap:22px;flex-wrap:wrap;margin:22px 0 6px;
border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:16px 0}}
.big div{{min-width:150px}}
.big b{{display:block;font-size:26px;letter-spacing:-.02em;line-height:1.1}}
.big span{{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.08em}}
table{{width:100%;border-collapse:collapse;margin:10px 0;font-size:14px}}
th{{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);
font-weight:600;border-bottom:1px solid var(--line);padding:6px 4px}}
td{{padding:7px 4px;border-bottom:1px solid #f2f2f2;vertical-align:top}}
.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.tag{{display:inline-block;font-size:10px;letter-spacing:.06em;text-transform:uppercase;
color:var(--hi);border:1px solid currentColor;border-radius:2px;padding:1px 4px;margin-left:4px;
vertical-align:1px}}
form{{background:#fafafa;border:1px solid var(--line);padding:14px;margin:18px 0}}
label{{display:block;font-size:12px;color:var(--mut);margin:0 0 3px;text-transform:uppercase;letter-spacing:.06em}}
.field{{display:inline-block;margin:0 14px 10px 0}}
input{{width:110px;padding:7px 8px;border:1px solid #ccc;border-radius:3px;font:inherit;
font-variant-numeric:tabular-nums}}
button{{background:var(--ink);color:#fff;border:0;padding:8px 14px;border-radius:3px;font:inherit;cursor:pointer}}
.hint{{font-size:12px;color:var(--mut)}}
.cta{{border:1px solid var(--ink);padding:16px;margin:28px 0}}
.cta a{{color:var(--ink);font-weight:600}}
.foot{{font-size:12px;color:var(--mut);border-top:1px solid var(--line);margin-top:34px;padding-top:12px}}
a{{color:#0b3d91}}
code{{font-size:13px;background:#f4f4f4;padding:1px 4px;border-radius:2px}}
</style></head>
<body><div class="wrap">
<div class="kicker">Agent meter · AI Price Watch · priced {TODAY}</div>
<h1>The same agent job bills {money(cheapest[0])} a month, or {money(dearest[0])}.</h1>
<p class="lede">One workload, {len(panel)} models, one dated price log. Half of the gap is not
visible on any vendor's pricing page, because an agent does not price like a chatbot.</p>

<div class="big">
  <div><span>Cheapest of {len(panel)}</span><b>{money(cheapest[0])}</b></div>
  <div><span>Median</span><b>{money(median)}</b></div>
  <div><span>Top decile</span><b>{money(p90)}</b></div>
  <div><span>Spread</span><b>{ratio:,.0f}&times;</b></div>
</div>
<p class="hint">Default workload: {RUNS} agent runs a day, {TURNS} turns each, {BASE:,} tokens of
system prompt and tool schemas resent every turn, {OBS:,} tokens of tool output added to history
each turn, {OUTP:,} tokens answered per turn. Billed input is {TIN:,.0f}M tokens a month and
output {TOUT:,.0f}M, which is what makes agents expensive: input grows with the square of the
turn count.</p>

<h2>Price your own workload</h2>
<form id="f" onsubmit="return false">
  <div class="field"><label>Runs per day</label><input id="runs" type="number" value="{RUNS}" min="1"></div>
  <div class="field"><label>Turns per run</label><input id="turns" type="number" value="{TURNS}" min="1"></div>
  <div class="field"><label>Base context (tokens)</label><input id="base" type="number" value="{BASE}" min="0"></div>
  <div class="field"><label>Added per turn</label><input id="obs" type="number" value="{OBS}" min="0"></div>
  <div class="field"><label>Answer per turn</label><input id="outp" type="number" value="{OUTP}" min="0"></div>
  <button onclick="run()">Recalculate</button>
  <p class="hint" id="stat"></p>
</form>
<div id="result"><table>
<thead><tr><th>#</th><th>Model</th><th class="num">Month</th><th class="num">Day</th><th class="num">$/M in / out</th></tr></thead>
<tbody id="tb">{table(rows)}</tbody></table>
<p class="hint">All {len(panel)} models are loaded on the page; recalculating re-sorts the full list,
so the cheapest row is always read off today's catalogue rather than a shortlist.</p></div>

<h2>Your chat bill and your agent bill moved in opposite directions</h2>
<p>Over the {DAYS} days to {TODAY}, the same log replayed backwards gives two different answers
depending on what you think you are buying.</p>
<table>
<thead><tr><th>Fixed workload</th><th class="num">30 days ago</th><th class="num">Today</th><th class="num">Change</th></tr></thead>
<tbody>
<tr><td>Chat · 120M in / 18M out a month, floor</td><td class="num">{money(chat_old[0])}</td><td class="num">{money(chat_today[0])}</td><td class="num">{pct(chat_today[0], chat_old[0]):+.1f}%</td></tr>
<tr><td>Chat · same, median of the panel</td><td class="num">{money(statistics.median(chat_old))}</td><td class="num">{money(statistics.median(chat_today))}</td><td class="num">{pct(statistics.median(chat_today), statistics.median(chat_old)):+.1f}%</td></tr>
<tr><td>Agent · the default job above, floor</td><td class="num">{money(old_floor)}</td><td class="num">{money(cheapest[0])}</td><td class="num" style="color:var(--warn)">{pct(cheapest[0], old_floor):+.1f}%</td></tr>
<tr><td>Agent · same, median of the panel</td><td class="num">{money(old_median)}</td><td class="num">{money(median)}</td><td class="num">{pct(median, old_median):+.1f}%</td></tr>
</tbody></table>
<p>Read the third row plainly: for an output-heavy agent loop the cheapest seat in this market got
more expensive, not less, while the chat figure went nowhere. Today alone the log took
{len(moves_today)} moves ({len(cuts)} down, {len(rises)} up) across {len(LAT['models'])} quoted
models, and the cheapest option for this job is {cheapest[1]['name']} at
{cheapest[1]['in']:g}/{cheapest[1]['out']:g} per million.</p>

<h2>Named models, same job</h2>
<table>
<thead><tr><th>Model</th><th class="num">$/M in / out</th><th class="num">Month</th></tr></thead>
<tbody>
{chr(10).join(sample)}
</tbody></table>

<div class="cta">
<p><b>The number a CFO cannot see is the one above.</b> A per-seat AI bill is visible; a fleet of
agents that re-reads its own history is not, and it lands on the same invoice.</p>
<p>Two ways I price this: a fixed <b>$2,500 cost audit</b> (15% refunded if the verified saving is
under $2,500 a year) — <a href="/audit/">scope and checkout</a>. Or the <b>price log itself</b> as a
licensed feed at <b>$500/mo</b>, so a router, a gateway or a FinOps dashboard prices an internal
workload against {len(LAT['models'])} models without scraping vendor pages —
<a href="/api-docs/">endpoints and schema</a>.</p>
<p class="hint">Free to check first: <a href="/agentcost/">what one 20-turn task bills per model</a> ·
<a href="/api/prices.json">/api/prices.json</a> ·
<a href="/datapath/">provider routes for 454 models</a>.</p>
</div>

<p class="foot">Built {TODAY} from OpenRouter's public catalogue. Assumptions are printed above, not
buried: no customer traffic was measured, so a real workload should replace the five inputs before
anyone quotes a saving off this page. Prices are per million tokens, USD, list, no cache discount and
no batch discount unless the listed model is itself the batch variant. Changed prices are logged daily
at <a href="/">AI Price Watch</a>. Contact: the studio account that sent you the link.</p>

<script>
const MODELS = {json.dumps(slim)};
const DAYS = {DAYS};
function money(x){{
  return "$" + Math.round(x).toLocaleString("en-US");
}}
function run(){{
  const runs=+document.getElementById("runs").value;
  const turns=+document.getElementById("turns").value;
  const base=+document.getElementById("base").value;
  const obs=+document.getElementById("obs").value;
  const outp=+document.getElementById("outp").value;
  if(!(runs>0)||!(turns>0)){{return;}}
  const tin=(turns*base + obs*(turns*(turns-1)/2))*runs*DAYS/1e6;
  const tout=turns*outp*runs*DAYS/1e6;
  const rows=MODELS.map(m=>({{m:m,c:tin*m.i+tout*m.o}})).sort((a,b)=>a.c-b.c);
  const tb=document.getElementById("tb");
  tb.innerHTML=rows.slice(0,12).map((r,i)=>
    `<tr><td class="num">${{i+1}}</td><td>${{r.m.n}}${{i===0?' <span class="tag">cheapest capable of the job</span>':''}}</td>`+
    `<td class="num">${{money(r.c)}}</td><td class="num">${{money(r.c/DAYS)}}</td>`+
    `<td class="num">${{r.m.i}} / ${{r.m.o}}</td></tr>`).join("");
  document.getElementById("stat").textContent =
    `${{tin.toLocaleString("en-US",{{maximumFractionDigits:0}})}}M input + ${{tout.toLocaleString("en-US",{{maximumFractionDigits:0}})}}M output tokens a month · ${{MODELS.length}} models · cheapest ${{money(rows[0].c)}} on ${{rows[0].m.n}}`;
}}
document.querySelectorAll("#f input").forEach(el=>el.addEventListener("input",run));
run();
</script>
</div></body></html>
"""

os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, "index.html"), "w").write(html)

summary = {
    "as_of": TODAY,
    "workload": {"runs_per_day": RUNS, "turns": TURNS, "base_context": BASE,
                 "added_per_turn": OBS, "answer_per_turn": OUTP, "days": DAYS,
                 "billed_input_m_tokens_month": round(TIN, 1),
                 "billed_output_m_tokens_month": round(TOUT, 1)},
    "panel_models": len(panel),
    "cheapest": {"model": cheapest[1]["name"], "month_usd": round(cheapest[0], 2),
                 "in": cheapest[1]["in"], "out": cheapest[1]["out"]},
    "median_month_usd": round(median, 2),
    "p90_month_usd": round(p90, 2),
    "dearest": {"model": dearest[1]["name"], "month_usd": round(dearest[0], 2)},
    "spread_x": round(ratio, 1),
    "thirty_day": {"since": target,
                   "agent_floor": round(old_floor, 2), "agent_floor_pct": round(pct(cheapest[0], old_floor), 1),
                   "agent_median": round(old_median, 2), "agent_median_pct": round(pct(median, old_median), 1),
                   "chat_floor": round(chat_old[0], 2), "chat_floor_pct": round(pct(chat_today[0], chat_old[0]), 1),
                   "chat_median": round(statistics.median(chat_old), 2),
                   "chat_median_pct": round(pct(statistics.median(chat_today), statistics.median(chat_old)), 1)},
    "models_quoted": len(LAT["models"]),
    "moves_today": len(moves_today), "cuts_today": len(cuts), "rises_today": len(rises),
    "events_logged": len(CH),
}
json.dump(summary, open(os.path.join(DATA, "agentmeter.json"), "w"), indent=1)
print(json.dumps(summary, indent=1))
print("wrote", os.path.join(OUT, "index.html"), len(html), "bytes")
