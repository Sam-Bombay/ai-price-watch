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
  echo "no price changes logged today"
  exit 0
fi

# something moved — publish it
git add -A data >/dev/null 2>&1
git -c user.email=sambombayoffice@gmail.com -c user.name="Sam Bombay" \
    commit -q -m "prices: $(date +%Y-%m-%d)" >/dev/null 2>&1
git push -q origin main >/dev/null 2>&1 || echo "push failed (page may lag)"

BIG=$("$PY" - <<'PY'
import json, datetime
d = json.load(open('/Users/sambombay/money-ideas/tracker/data/changes.json'))
today = datetime.datetime.utcnow().strftime('%Y-%m-%d')
big = [c for c in d if c['date'] == today and c.get('field') == 'output' and (c.get('pct') or 0) <= -10]
for c in big[:5]:
    print(f"{c['name']} {c['field']} {c['from']} -> {c['to']} ({c['pct']}%)")
print(len(big))
PY
)
COUNT=$(echo "$BIG" | tail -1)
LINES=$(echo "$BIG" | sed '$d')
echo "logged changes: $(echo "$OUT" | head -1)"

if [ "${COUNT:-0}" -gt 0 ]; then
  /Users/sambombay/money-ideas/send_tg.py "AI Price Watch — big move today

$LINES

Full log: https://ai-price-watch-beta.vercel.app" >/dev/null 2>&1 && echo "pinged (${COUNT} big cuts)"
fi
