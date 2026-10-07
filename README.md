# AI Price Watch

A daily-updated log of price changes across the AI model market, and what every model costs
per million tokens right now.

- `fetch_prices.py` — snapshots OpenRouter's public model catalogue, diffs it against the
  previous run, and appends every price change / new / retired model to `data/changes.json`.
- `data/latest.json` — the table the public page renders.
- `data/snapshot.json` — prior state used for diffing.

Run it: `./fetch_prices.py` (no API key needed — the catalogue endpoint is public).
