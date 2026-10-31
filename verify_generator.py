#!/usr/bin/env python3
"""Check /msp/generator's in-page arithmetic against an independent Python implementation.

The page computes the report in the browser from the embedded model table, so the numbers have to
be right in JavaScript, not just in Python. This pulls the real MODELS blob and the real
computeReport function out of the built HTML, runs them in node with the same inputs, and compares
against the Python mirror. Exits non-zero on any disagreement.

Usage: /usr/bin/python3 verify_generator.py
"""
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML = open(os.path.join(ROOT, 'msp/generator/index.html')).read()

mj = re.search(r'const MODELS = (\[.*?\]);\n', HTML, re.S)
fj = re.search(r'function computeReport\(inp, models\)\{(.*?)\n\}\n', HTML, re.S)
if not mj or not fj:
    sys.exit('FAIL: could not extract MODELS or computeReport from the built page')

models_json = mj.group(1)
fn_src = 'function computeReport(inp, models){' + fj.group(1) + '\n}\n'
models = json.loads(models_json)
by_id = {m['id']: m for m in models}

CASES = [
    (2000.0, 'openai/gpt-5.2'),
    (2000.0, 'anthropic/claude-sonnet-4.5'),
    (45000.0, 'openai/gpt-5.5-pro'),
    (300.0, 'openai/gpt-5-mini'),
    (9000.0, 'google/gemini-2.5-pro'),
    (0.0, 'openai/gpt-5.2'),
]

blended_of = lambda m: 0.75 * m['i'] + 0.25 * m['o']
tier_of = lambda b: 2 if b >= 8 else (1 if b >= 1 else 0)


def py_report(spend, cur_id):
    cur = by_id[cur_id]
    tier = tier_of(blended_of(cur))
    volume = spend / blended_of(cur) if blended_of(cur) > 0 else 0.0
    tin, tout = volume * 0.75, volume * 0.25
    q = [m for m in models if (m['c'] or 0) >= 128000]
    in_class = sorted(((m, tin * m['i'] + tout * m['o']) for m in q
                       if tier_of(blended_of(m)) == tier), key=lambda x: x[1])
    allq = sorted(((m, tin * m['i'] + tout * m['o']) for m in q), key=lambda x: x[1])
    best, floor = in_class[0]
    median = in_class[len(in_class) // 2][1]
    fair = min(spend, median)
    save = max(0.0, spend - fair)
    return {'fair': round(fair, 6), 'floor': round(floor, 6), 'median': round(median, 6),
            'saveYr': round(save * 12, 6),
            'ceilingYr': round(max(0.0, spend - allq[0][1]) * 12, 6),
            'best': best['id'], 'classN': len(in_class)}


js = fn_src + '\nconst MODELS = ' + models_json + ';\n' + \
     'const cases = ' + json.dumps([{'spend': s, 'curModel': c, 'seats': 0} for s, c in CASES]) + ';\n' + \
     'const out = cases.map(i => { const r = computeReport(i, MODELS); return {' \
     'fair: r.fair, floor: r.floor, median: r.median, saveYr: r.saveYr, ceilingYr: r.ceilingYr, ' \
     'best: r.best.id, classN: r.classN}; });\n' \
     'console.log(JSON.stringify(out));\n'

with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
    f.write(js)
    path = f.name

try:
    res = subprocess.run(['node', path], capture_output=True, text=True, timeout=120)
except FileNotFoundError:
    sys.exit('FAIL: node not installed, cannot verify the page arithmetic')
finally:
    os.unlink(path)

if res.returncode != 0:
    sys.exit('FAIL: node error\n' + res.stderr[:2000])

js_out = json.loads(res.stdout)
bad = 0
for (spend, cid), got in zip(CASES, js_out):
    want = py_report(spend, cid)
    for k in ('fair', 'floor', 'median', 'saveYr', 'ceilingYr'):
        if abs(got[k] - want[k]) > 0.01:
            print(f"MISMATCH {cid} spend={spend} {k}: js={got[k]} py={want[k]}")
            bad += 1
    if got['best'] != want['best'] or got['classN'] != want['classN']:
        print(f"MISMATCH {cid} spend={spend} best/classN: js={got['best']}/{got['classN']} "
              f"py={want['best']}/{want['classN']}")
        bad += 1
    print(f"ok {cid} ${spend:,.0f}/mo: class middle=${got['fair']:,.2f} "
          f"annual gap=${got['saveYr']:,.0f} ceiling=${got['ceilingYr']:,.0f} "
          f"classN={got['classN']} best={got['best']}")

# sanity rails: a like-for-like report must never claim a fantasy multiple
for (spend, cid), got in zip(CASES, js_out):
    if spend > 0 and got['fair'] > 0:
        mult = spend / got['fair']
        if mult > 12:
            print(f"IMPLAUSIBLE {cid} ${spend:,.0f}/mo: class middle implies {mult:.1f}x")
            bad += 1

if bad:
    sys.exit(f'FAIL: {bad} problems')
print(f'PASS: node and python agree on {len(CASES)} cases, no implausible multiples')
