#!/bin/bash
# Daily upkeep for AI Price Watch: snapshot the market, log changes, publish.
# Silent on quiet days. Pings Sam only when a price moved hard (>=10%), because that is the
# moment the page has something worth telling him.
set -uo pipefail
cd /Users/sambombay/money-ideas/tracker || exit 1
PY=/usr/bin/python3

BEFORE=$(cat data/changes.json 2>/dev/null | wc -c | tr -d ' ')
OUT=$("$PY" ./fetch_prices.py) || { echo "price fetch failed: $OUT"; exit 1; }
AFTER=$(cat data/changes.json | wc -c | tr -d ' ')

if [ "$BEFORE" = "$AFTER" ]; then
  ./publish_gh_pages.sh >/dev/null 2>&1 || echo "pages mirror failed"
  echo "no price changes logged today"
  exit 0
fi

# something moved — publish it
git add -A data >/dev/null 2>&1
git -c user.email=sambombayoffice@gmail.com -c user.name="Sam Bombay" \
    commit -q -m "prices: $(date +%Y-%m-%d)" >/dev/null 2>&1
git push -q origin main >/dev/null 2>&1 || echo "push failed (page may lag)"

# git push alone does NOT deploy this project — it needs an explicit prod deploy.
# Verified 13 Oct 2026: pushes sat unbuilt and the live page was a day stale until this ran.
if command -v vercel >/dev/null 2>&1; then
  vercel --prod --yes >/dev/null 2>&1 && echo "deployed" || echo "deploy failed (page may lag)"
fi

# second home: free GitHub Pages mirror, so the funnel survives any Vercel billing lapse
./publish_gh_pages.sh >/dev/null 2>&1 && echo "pages mirrored" || echo "pages mirror failed"

BIG=$("$PY" - <<'PY'
import json, datetime
d = json.load(open('/Users/sambombay/money-ideas/tracker/data/changes.json'))
today = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
big = [c for c in d if c['date'] == today and c.get('field') == 'output' and (c.get('pct') or 0) <= -10]
for c in big[:5]:
    print(f"{c['name']} {c['field']} {c['from']} -> {c['to']} ({c['pct']}%)")
print(len(big))
PY
)
COUNT=$(echo "$BIG" | tail -1)
LINES=$(echo "$BIG" | sed '$d')
echo "logged changes: $(echo "$OUT" | head -1)"

# refresh the RSS feed from the briefs, so the feed is never staler than the page
"$PY" ./gen_feed.py >/dev/null 2>&1 || echo "feed generation failed"

# third home: the log as a citable public dataset (Hugging Face). Distribution without
# asking anyone to click: analysts, newsletter writers and tooling authors can cite and
# re-publish it, and every citation points back at the funnel.
"$PY" ./build_dataset.py >/dev/null 2>&1 || echo "dataset build failed"
HFTOK=$(osascript -e 'tell application "Notes" to get body of note "API"' 2>/dev/null \
        | sed 's/<[^>]*>//g' | grep -o "hf_[A-Za-z0-9]\{20,\}" | head -1)
if [ -n "${HFTOK:-}" ] && command -v hf >/dev/null 2>&1; then
  HF_TOKEN="$HFTOK" hf upload sambombay/ai-model-price-changes dataset --repo-type dataset \
    >/dev/null 2>&1 && echo "dataset published" || echo "dataset upload failed"
fi

if [ "${COUNT:-0}" -gt 0 ]; then
  /Users/sambombay/money-ideas/send_tg.py "AI Price Watch — big move today

$LINES

Full log: https://ai-price-watch-beta.vercel.app" >/dev/null 2>&1 && echo "pinged (${COUNT} big cuts)"
fi
