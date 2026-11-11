#!/usr/bin/env python3
"""
/seatcost — what ONE engineer's AI coding bill is, and what the same token volume
costs on the open-weight models.

Built 04 Nov 2026. Why: /selfhost answers the CFO's question (rent GPUs or pay per
token). It does not answer the engineering manager's question, which is the one being
asked this week after Revolut's talk went mainstream: "my devs are on Claude Code, one
of them is $1,000-$10,000 a month — what is normal, and what is the same work worth
elsewhere?"

Every number here is computed from the same live catalogue the daily cron refreshes
(data/latest.json). No benchmark is claimed. Token mix is a stated assumption with a
visible sensitivity, because we have not measured any customer's real traffic.
"""
import json
import os
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "seatcost")

# Claude Code-like coding traffic is read-heavy: long files in, short diffs out.
# 10:1 is the stated default, exposed as a slider in the page. NOT measured.
IN_OUT_RATIO = 10

# Models we quote as "what you are probably on", and the swaps. Every id must exist
# in the catalogue; the builder fails loudly if one is retired instead of silently
# printing a blank.
BASELINE = ["anthropic/claude-opus-5.5", "anthropic/claude-sonnet-5.5", "anthropic/claude-sonnet-4.6"]
SWAPS = ["z-ai/glm-5.3", "z-ai/glm-5.3-flash", "deepseek/deepseek-v4.1-flash",
         "qwen/qwen3-coder", "moonshotai/kimi-k2.7-code"]

# Tier matters more than price. A small/fast model is not a like-for-like swap for
# Opus on a hard refactor, so the headline saving is computed ONLY against models in
# the same class. Cheap-tier numbers are shown, labelled, and never used as the
# headline — an audit that promises a 90x cut is a sales lie, not an audit.
TIER = {
    "anthropic/claude-opus-5.5": "frontier",
    "anthropic/claude-sonnet-5.5": "frontier",
    "anthropic/claude-sonnet-4.6": "frontier",
    "z-ai/glm-5.3": "large",
    "qwen/qwen3-coder": "large",
    "moonshotai/kimi-k2.7-code": "large",
    "z-ai/glm-5.3-flash": "small",
    "deepseek/deepseek-v4.1-flash": "small",
}
# A same-class swap that implies a bigger cut than this is treated as an error and
# fails the build, not printed.
MAX_CREDIBLE_CUT = 12.0

LABELS = {
    "anthropic/claude-opus-5.5": "Claude Opus 5.5",
    "anthropic/claude-sonnet-5.5": "Claude Sonnet 5.5",
    "anthropic/claude-sonnet-4.6": "Claude Sonnet 4.6",
    "z-ai/glm-5.3": "GLM 5.3",
    "z-ai/glm-5.3-flash": "GLM 5.3 Flash",
    "deepseek/deepseek-v4.1-flash": "DeepSeek V4.1 Flash",
    "qwen/qwen3-coder": "Qwen3 Coder",
    "moonshotai/kimi-k2.7-code": "Kimi K2.7 Code",
}


def load():
    d = json.load(open(os.path.join(DATA, "latest.json")))
    return {m["id"]: m for m in d["models"]}, d.get("updated", "")


def cost_per_mt(inp, out, ratio=IN_OUT_RATIO):
    """USD for one 'unit' of output token and `ratio` input tokens, in millions."""
    return (ratio * inp + out) / (ratio + 1) * 1.0


def main():
    models, updated = load()
    rows = []
    for mid in BASELINE + SWAPS:
        m = models.get(mid)
        if not m or not m.get("in") or not m.get("out"):
            raise SystemExit(f"missing price for {mid} - refusing to build a page with a blank")
        rows.append({
            "id": mid,
            "name": LABELS[mid],
            "in": m["in"],
            "out": m["out"],
            "ctx": m.get("ctx"),
            "blended": round(cost_per_mt(m["in"], m["out"]), 6),
            "group": "baseline" if mid in BASELINE else "swap",
            "tier": TIER[mid],
        })

    # Guard: a same-class swap implying an absurd cut means the catalogue moved under
    # us or a tier is mislabelled. Fail rather than ship a page that overclaims.
    base_blend = next(r["blended"] for r in rows if r["id"] == "anthropic/claude-sonnet-5.5")
    for r in rows:
        if r["tier"] == "large":
            cut = base_blend / r["blended"]
            if cut > MAX_CREDIBLE_CUT:
                raise SystemExit(f"implausible same-class cut {cut:.1f}x for {r['id']} - check tiers")

    payload = {
        "updated": updated,
        "generated": datetime.datetime.now().strftime("%Y-%m-%d"),
        "ratio": IN_OUT_RATIO,
        "models": rows,
    }

    os.makedirs(OUT, exist_ok=True)
    html = TEMPLATE.replace("__DATA__", json.dumps(payload))
    with open(os.path.join(OUT, "index.html"), "w") as f:
        f.write(html)

    # cheque: what $1,000/engineer looks like on each baseline, and the swap price
    for r in rows:
        pass
    print(f"wrote {OUT}/index.html  models={len(rows)}  updated={updated}")
    for r in rows:
        print(f"  {r['name']:22s} in ${r['in']:>8} out ${r['out']:>8}  blended ${r['blended']:.4f}/M")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>What one engineer's AI coding bill should be — live model prices</title>
<meta name="description" content="Enter what your team spends on AI coding tools. See the same token volume priced on today's Claude, GLM, DeepSeek and Qwen rates, from a daily-updated catalogue.">
<style>
:root{--ink:#111;--dim:#666;--line:#e3e3e3;--bg:#fff;--accent:#0a6c4f;--warn:#8a4b00}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:30px;line-height:1.2;margin:0 0 8px;letter-spacing:-.02em}
h2{font-size:18px;margin:34px 0 10px;letter-spacing:-.01em}
.sub{color:var(--dim);margin:0 0 26px}
.controls{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:22px 0 4px}
@media(max-width:600px){.controls{grid-template-columns:1fr}}
label{display:block;font-size:13px;color:var(--dim);margin-bottom:5px}
input[type=number],select{width:100%;padding:10px 12px;font-size:17px;border:1px solid var(--line);border-radius:8px;background:#fafafa;font-family:inherit;color:var(--ink)}
input[type=range]{width:100%}
table{width:100%;border-collapse:collapse;margin-top:12px;font-size:15px}
th,td{text-align:right;padding:9px 6px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
th{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--dim);font-weight:600}
tr.pick{background:#f3faf7}
td.save{color:var(--accent);font-weight:600}
.big{display:flex;gap:32px;flex-wrap:wrap;margin:18px 0 6px}
.kpi{flex:1;min-width:150px}
.kpi .n{font-size:30px;font-weight:700;letter-spacing:-.02em}
.kpi .l{font-size:13px;color:var(--dim)}
.note{font-size:13px;color:var(--dim);border-left:2px solid var(--line);padding-left:14px;margin:22px 0}
.warn{color:var(--warn)}
.cta{margin:36px 0 0;padding:20px;border:1px solid var(--line);border-radius:10px;background:#fafafa}
.cta a{color:var(--accent)}
.bookmark{font-size:12px;color:var(--dim);text-transform:uppercase;letter-spacing:.05em}
input[type=range]{accent-color:var(--accent)}
</style>
</head>
<body>
<div class="wrap">

<p class="bookmark">Live prices, generated <span id="gen"></span></p>
<h1>What one engineer's AI coding bill actually costs</h1>
<p class="sub">Claude Code and Cursor bills are now a line item people get asked about. Enter
what your team spends and this prices the <em>same token volume</em> on today's open-weight
models. Every figure comes from a catalogue refreshed daily from public provider pricing.</p>

<div class="controls">
  <div>
    <label for="spend">Monthly AI spend per engineer (USD)</label>
    <input type="number" id="spend" value="1000" min="0" step="50">
  </div>
  <div>
    <label for="team">Engineers using it</label>
    <input type="number" id="team" value="12" min="1" step="1">
  </div>
  <div>
    <label for="base">What you run today</label>
    <select id="base">
      <option value="anthropic/claude-sonnet-5.5" selected>Claude Sonnet 5.5</option>
      <option value="anthropic/claude-opus-5.5">Claude Opus 5.5</option>
      <option value="anthropic/claude-sonnet-4.6">Claude Sonnet 4.6</option>
    </select>
  </div>
</div>
<div style="margin-top:16px">
  <label for="ratio">Input tokens per output token: <span id="rlabel">10</span> : 1</label>
  <input type="range" id="ratio" min="2" max="30" value="10" step="1">
</div>

<div class="big">
  <div class="kpi"><div class="n" id="cur">$12,000</div><div class="l">your bill today, per month</div></div>
  <div class="kpi"><div class="n" id="best">$—</div><div class="l">cheapest same-volume equivalent</div></div>
  <div class="kpi"><div class="n" id="save">$—</div><div class="l">annual difference</div></div>
</div>

<h2>Same tokens, different price list</h2>
<table>
<thead><tr><th>Model</th><th>In / out per M</th><th>Blended / M</th><th>Team / month</th><th>vs your bill</th></tr></thead>
<tbody id="rows"></tbody>
</table>

<div class="note">
Blended price assumes <b><span id="ratio2">10</span> input tokens per output token</b>, which is
what read-heavy coding traffic looks like. Pull the slider to your own traffic mix — the ranking
holds, the gap moves. Nothing here is a benchmark, and no traffic of yours was seen to produce it.
</div>

<div class="note warn">
Honest limits. Price is not the same as fitness: GLM 5.3 and DeepSeek are text-only, so they do
not do UI or screenshot work, and a team that swaps everything will hit that wall inside a week.
The pattern that actually works — and the one Revolut described on 30 Oct 2026 — is a router:
cheap open-weight models for code generation, a frontier model held back for the exceptions and
for anything visual. Budget caps alone backfire; Revolut said engineers responded to caps by
rationing tokens and using AI less, which is the expensive outcome dressed as thrift.
</div>

<div class="cta">
<p style="margin:0 0 8px"><b>The audit, priced honestly.</b> Send one redacted month of your AI
bill. I return the line-by-line: what your traffic actually is, which routes to swap, what the
swap is worth per engineer, and which spend is dead. You keep 70% of what is verified as saved.
My own audit cut $5,988/yr across four line items and every one is dated:
<a href="/receipts">/receipts</a>.</p>
<p style="margin:0;font-size:14px;color:#666">Arithmetic you can re-run: <a href="/selfhost">/selfhost</a>
for rent-vs-token at your volume, <a href="/repricing">/repricing</a> for a vendor re-bid email,
<a href="/benchmark">/benchmark</a> for the spread across the market.</p>
</div>

<p class="note" style="border:0;padding:0;margin-top:30px">Prices: OpenRouter public catalogue,
snapshot <span id="upd"></span>. Built from the same log as the daily AI price brief.
No paid inference was used to generate this page.</p>

</div>
<script>
const D = __DATA__;
document.getElementById('gen').textContent = D.generated;
document.getElementById('upd').textContent = D.updated;

const el = id => document.getElementById(id);
const money = n => '$' + Math.round(n).toLocaleString('en-US');

function calc(){
  const spend = Math.max(0, +el('spend').value || 0);
  const team   = Math.max(1, +el('team').value || 1);
  const ratio  = +el('ratio').value || D.ratio;
  el('rlabel').textContent = ratio;
  el('ratio2').textContent = ratio;
  el('cur').textContent = money(spend * team);

  const base = D.models.find(m => m.id === el('base').value);
  // token volume implied by the user's spend, priced at their current list
  const perM = (ratio * base.in + base.out) / (ratio + 1);
  const millionUnits = perM > 0 ? spend / perM : 0;   // millions of output-equivalent units

  const priced = D.models.map(m => {
    const blend = (ratio * m.in + m.out) / (ratio + 1);
    const monthly = blend * millionUnits * team;
    return {...m, blend, monthly};
  }).sort((a,b) => a.monthly - b.monthly);

  const curTotal = spend * team;
  // headline uses SAME-CLASS models only. Cheaper tiers exist and are shown, but
  // quoting a small model's price as "your saving" would be a lie about the work.
  const sameClass = priced.filter(p => p.tier === 'large');
  const best = Math.min(...sameClass.map(p => p.monthly));
  el('best').textContent = money(best);
  el('save').textContent = money((curTotal - best) * 12);

  const tierLabel = t => t === 'small' ? 'small / fast' : t === 'large' ? 'large' : 'frontier';
  el('rows').innerHTML = priced.map(p => {
    const diff = curTotal - p.monthly;
    const cls = (p.tier === 'large') ? 'pick' : '';
    const d = diff > 0 ? '<span class="save">' + money(diff) + '</span>' : '—';
    return `<tr class="${cls}"><td>${p.name}<br><span style="font-size:12px;color:#888">${tierLabel(p.tier)}</span></td>
      <td>$${p.in} / $${p.out}</td>
      <td>$${p.blend.toFixed(3)}</td>
      <td>${money(p.monthly)}</td>
      <td>${d}</td></tr>`;
  }).join('');
}
['spend','team','ratio','base'].forEach(id => {
  el(id).addEventListener('input', calc);
  el(id).addEventListener('change', calc);
});
calc();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
