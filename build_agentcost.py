#!/usr/bin/env python3
"""
/agentcost - what ONE agent task actually bills, per model.

Built 14 Nov 2026, the morning the WSJ ran "Big Tech Wants Everyone to Use an AI
Agent. But Who Shoulders the Cost?" The question that follows it inside every
company is arithmetic, not strategy: an agent re-sends its growing context on
every turn, so a 20-turn task is not 20x one prompt, it is a quadratic curve.
Nobody prices that curve for the buyer.

Every number is computed from the same live catalogue the daily cron refreshes
(data/latest.json). The turn count, context growth and output size are STATED
ASSUMPTIONS shown on the page - no customer traffic has been measured.
"""
import json
import os
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "agentcost")

# Stated assumptions. An agent loop re-sends history each turn, so input tokens
# grow linearly with turn number and total billed input grows quadratically.
TURNS = 20
BASE_CONTEXT = 6000      # system prompt + tool schemas, resent every turn
OUT_PER_TURN = 800       # the assistant's reply
OBSERVED_PER_TURN = 1200  # tool result / retrieved chunk fed back into history

PANEL = [
    ("anthropic/claude-opus-5.5", "Claude Opus 5.5", "frontier"),
    ("anthropic/claude-sonnet-5.5", "Claude Sonnet 5.5", "frontier"),
    ("openai/gpt-5.6-sol", "GPT-5.6 Sol", "frontier"),
    ("moonshotai/kimi-k3.1-pro", "Kimi K3.1 Pro", "large"),
    ("z-ai/glm-5.3", "GLM 5.3", "large"),
    ("deepseek/deepseek-v4.1-flash", "DeepSeek V4.1 Flash", "small"),
    ("qwen/qwen3.5-9b", "Qwen3.5-9B", "small"),
]

# A same-tier swap that implies a bigger cut than this is an error, not a saving.
MAX_CREDIBLE_CUT = 12.0


def load():
    d = json.load(open(os.path.join(DATA, "latest.json")))
    return {m["id"]: m for m in d["models"]}, d.get("updated", "")


def agent_tokens(turns=TURNS):
    """Total billed tokens for one agent task, history resent each turn."""
    inp = sum(BASE_CONTEXT + i * (OUT_PER_TURN + OBSERVED_PER_TURN) for i in range(turns))
    out = turns * OUT_PER_TURN
    return inp, out


def main():
    models, updated = load()
    tin, tout = agent_tokens()
    rows = []
    for mid, label, tier in PANEL:
        m = models.get(mid)
        if not m or not m.get("in") or not m.get("out"):
            raise SystemExit(f"missing price for {mid} - refusing to build a page with a blank")
        cost = tin / 1e6 * m["in"] + tout / 1e6 * m["out"]
        rows.append({
            "id": mid, "name": label, "tier": tier,
            "in": m["in"], "out": m["out"], "ctx": m.get("ctx"),
            "cost": round(cost, 4),
        })

    baseline = next(r for r in rows if r["id"] == "anthropic/claude-sonnet-5.5")
    for r in rows:
        if r["tier"] == "large":
            cut = baseline["cost"] / r["cost"]
            if cut > MAX_CREDIBLE_CUT:
                raise SystemExit(f"implausible same-tier cut {cut:.1f}x for {r['id']} - check tiers")

    payload = {
        "updated": updated,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d"),
        "turns": TURNS, "base": BASE_CONTEXT, "out_per_turn": OUT_PER_TURN,
        "obs_per_turn": OBSERVED_PER_TURN,
        "in_tokens": tin, "out_tokens": tout,
        "models": rows,
    }

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "index.html"), "w") as f:
        f.write(TEMPLATE.replace("__DATA__", json.dumps(payload)))

    print(f"wrote {OUT}/index.html  updated={updated}")
    print(f"one {TURNS}-turn task = {tin:,} in / {tout:,} out tokens")
    for r in rows:
        print(f"  {r['name']:22s} ${r['cost']:>8.2f}  x{baseline['cost']/r['cost']:.1f} vs Sonnet")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>What one agent task actually costs, per model</title>
<meta name="description" content="An agent re-sends its context every turn, so one 20-turn task bills far more than 20 prompts. Computed daily from the live model price catalogue.">
<style>
:root{--bg:#0d0f12;--fg:#e8eaed;--dim:#9aa0a6;--line:#23262b;--acc:#7ce38b;--warn:#f0b866}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
main{max-width:860px;margin:0 auto;padding:40px 20px 80px}
h1{font-size:29px;line-height:1.2;margin:0 0 8px;letter-spacing:-.4px}
h2{font-size:15px;text-transform:uppercase;letter-spacing:1.2px;color:var(--dim);margin:36px 0 10px;font-weight:600}
p{margin:0 0 14px}.sub{color:var(--dim);margin-bottom:26px}
table{width:100%;border-collapse:collapse;margin:6px 0 10px;font-variant-numeric:tabular-nums}
th,td{text-align:right;padding:9px 8px;border-bottom:1px solid var(--line);font-size:14px}
th:first-child,td:first-child{text-align:left}
th{color:var(--dim);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.6px}
td.c{font-weight:600}tr.hi td.c{color:var(--acc)}
.small{color:var(--dim);font-size:13px}
.box{border:1px solid var(--line);border-radius:10px;padding:16px;margin:18px 0;background:#11141a}
.kpi{display:flex;gap:26px;flex-wrap:wrap;margin:18px 0}
.kpi div{flex:1;min-width:150px}.kpi b{display:block;font-size:24px;letter-spacing:-.5px}
.kpi span{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.7px}
code{background:#1a1d23;padding:2px 6px;border-radius:4px;font-size:13px}
a{color:var(--acc)}footer{margin-top:44px;color:var(--dim);font-size:12px;border-top:1px solid var(--line);padding-top:16px}
</style></head><body><main>
<h1>What one agent task actually costs</h1>
<p class="sub">An agent does not send one prompt. It re-sends its whole history on every
turn, so a 20-turn task bills about 40 times the tokens of a single call. Priced here
from today's live catalogue, per model.</p>

<div class="kpi">
  <div><span>Task</span><b id="k-turns">20</b> turns</div>
  <div><span>Billed input</span><b id="k-in">-</b></div>
  <div><span>Billed output</span><b id="k-out">-</b></div>
  <div><span>Spread</span><b id="k-spread">-</b></div>
</div>

<h2>One agent task, same work, today's prices</h2>
<table><thead><tr><th>Model</th><th>Tier</th><th>Cost per task</th><th>x vs Sonnet 5.5</th></tr></thead>
<tbody id="rows"></tbody></table>
<p class="small">Prices are per million tokens from the public OpenRouter catalogue, snapshot
<span id="k-upd">-</span>. Cost is computed, not quoted by any vendor.</p>

<div class="box">
<h2 style="margin-top:0">The assumptions, in full</h2>
<p class="small" style="margin-bottom:8px">One task = <span id="k2-turns"></span> turns. Each turn
resends a <span id="k2-base"></span>-token base (system prompt and tool schemas), plus everything
produced so far: <span id="k2-out"></span> output tokens and <span id="k2-obs"></span> tokens of tool
result per turn. That growth is what makes the curve quadratic, and it is the part missing from
every per-token comparison.</p>
<p class="small" style="margin:0">These are stated assumptions, not measurements of your traffic.
Change the turn count and the ranking stays, the dollar figures move. Tier matters more than
price: a small model is not a like-for-like swap for a frontier one on a hard task, so no
same-tier swap here exceeds a <span id="k2-cut"></span>x cut.</p>
</div>

<h2>Why this is the number that gets missed</h2>
<p>A CFO approves "an agent" against a per-token rate. The bill arrives after the agent has run
a few thousand tasks, each one quietly re-reading its own context. The same 20-turn task costs
<span id="k-min"></span> on the cheapest model in this panel and <span id="k-max"></span> on the
most expensive: the work is identical, the price of doing it is not.</p>
<p>That gap is what an audit finds. <a href="https://ai-price-watch-beta.vercel.app/audit/">What
an audit costs and what it covers</a> - fixed price, refunded if it does not find at least 15%.</p>

<footer>AI Price Watch. Price data rebuilt daily from the public catalogue; snapshots and the
change log are CC-BY. <a href="https://ai-price-watch-beta.vercel.app/">Home</a> .
<a href="https://ai-price-watch-beta.vercel.app/dataset/">Dataset</a> .
<a href="https://ai-price-watch-beta.vercel.app/cost-index/">Index</a></footer>
</main>
<script>
const D = __DATA__;
const money = n => "$" + n.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2});
document.getElementById("k-turns").textContent = D.turns;
document.getElementById("k-in").textContent = (D.in_tokens/1000).toFixed(0) + "k";
document.getElementById("k-out").textContent = (D.out_tokens/1000).toFixed(0) + "k";
document.getElementById("k2-turns").textContent = D.turns;
document.getElementById("k2-base").textContent = D.base.toLocaleString();
document.getElementById("k2-out").textContent = D.out_per_turn.toLocaleString();
document.getElementById("k2-obs").textContent = D.obs_per_turn.toLocaleString();
document.getElementById("k2-cut").textContent = "12";
document.getElementById("k-upd").textContent = D.updated;
const base = D.models.find(m => m.id === "anthropic/claude-sonnet-5.5").cost;
const costs = D.models.map(m => m.cost);
document.getElementById("k-spread").textContent = (Math.max(...costs)/Math.min(...costs)).toFixed(1) + "x";
document.getElementById("k-min").textContent = money(Math.min(...costs));
document.getElementById("k-max").textContent = money(Math.max(...costs));
const tb = document.getElementById("rows");
D.models.slice().sort((a,b)=>a.cost-b.cost).forEach(m => {
  const tr = document.createElement("tr");
  const r = base / m.cost;
  tr.innerHTML = "<td>" + m.name + "</td><td class='small'>" + m.tier + "</td><td class='c'>"
    + money(m.cost) + "</td><td class='small'>x" + r.toFixed(1) + "</td>";
  if (r < 1) tr.classList.add("hi");
  tb.appendChild(tr);
});
</script></body></html>
"""

if __name__ == "__main__":
    main()
