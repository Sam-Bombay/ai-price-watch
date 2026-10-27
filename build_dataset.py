#!/usr/bin/env python3
"""Export the AI Price Watch log as a public, citable dataset.

Distribution asset: the change log is a primary source for anyone writing about AI
costs (newsletters, analysts, MSPs, tooling authors). Publishing it as a dated
dataset on Hugging Face makes it quotable without a single email being sent.

Writes: dataset/changes.csv, dataset/prices.csv, dataset/README.md
"""
import csv
import datetime
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dataset")
SITE = "https://ai-price-watch-beta.vercel.app"
REPO = "Sam-Bombay/ai-model-price-changes"


def load(name):
    with open(os.path.join(HERE, "data", name), encoding="utf-8") as f:
        d = json.load(f)
    return d if isinstance(d, list) else d.get("models", d.get("changes", []))


def main():
    os.makedirs(OUT, exist_ok=True)
    changes = load("changes.json")
    prices = load("latest.json")

    changes.sort(key=lambda c: (c.get("date", ""), c.get("name", "")))
    rows = []
    for c in changes:
        frm, to = c.get("from"), c.get("to")
        pct = ""
        if c.get("field") in ("input", "output") and frm and to:
            try:
                pct = round((to - frm) / frm * 100, 1)
            except ZeroDivisionError:
                pct = ""
        rows.append([c.get("date", ""), c.get("id", ""), c.get("name", ""),
                     c.get("field", ""), frm if frm is not None else "",
                     to if to is not None else "", pct])

    with open(os.path.join(OUT, "changes.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date", "model_id", "model_name", "field", "price_from", "price_to",
                    "pct_change"])
        w.writerows(rows)

    with open(os.path.join(OUT, "prices.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model_id", "model_name", "input_per_1m_usd", "output_per_1m_usd",
                    "context_window"])
        for m in sorted(prices, key=lambda x: str(x.get("name", ""))):
            w.writerow([m.get("id", ""), m.get("name", ""), m.get("in", ""),
                        m.get("out", ""), m.get("ctx", "")])

    dates = sorted({r[0] for r in rows if r[0]})
    first, last = (dates[0], dates[-1]) if dates else ("", "")
    n_price = sum(1 for r in rows if r[3] in ("input", "output"))
    price_rows = [r for r in rows if r[3] in ("input", "output") and r[6] != ""]
    cuts = sum(1 for r in price_rows if r[6] < 0)
    rises = sum(1 for r in price_rows if r[6] > 0)

    card = f"""---
license: cc-by-4.0
language:
  - en
tags:
  - ai
  - pricing
  - llm
  - economics
pretty_name: AI Model Price Changes
size_categories:
  - n<1K
---

# AI Model Price Changes

A daily log of retail price changes across the AI model market, derived from the public
[OpenRouter](https://openrouter.ai) model catalogue. One row per price event: which model,
which field, the price before, the price after.

Maintained by Sam Bombay / Noir & Co. Live view: {SITE}

## What is in it

- `changes.csv` - every logged change: `date, model_id, model_name, field, price_from, price_to, pct_change`.
  `field` is `input`, `output`, `added` (new model) or `retired` (withdrawn).
  All prices are USD per 1,000,000 tokens.
- `prices.csv` - the current snapshot: input and output price and context window per model.

Coverage: **{len(rows)} events** across **{len(prices)} models**, {first} to {last}.
Of {len(price_rows)} comparable price events, **{cuts} are cuts and {rises} are rises**.

## Why it is useful

AI list prices are not stable, and they do not all move in one direction. In this log the
same model routinely falls more than 20 percent and climbs straight back, while other models
are retired without notice. Anyone modelling AI unit economics, writing about AI costs, or
auditing a vendor invoice needs the dated record rather than today's rate card.

## Method and limits

- Source: the public OpenRouter model catalogue, fetched once a day.
- A change is logged when a model ID's `input` or `output` price differs from the previous
  fetch. New and retired model IDs are logged as `added` / `retired`.
- Prices are retail list prices in USD per 1M tokens. They are not invoice prices; discounts,
  committed-volume rates and enterprise agreements are not visible here.
- Catalogue aliases (for example a `Latest` pointer) are separate rows from the models they
  point at, and can move independently.
- Dated from the first fetch, not from a vendor announcement. A change logged on date D means
  the difference was observed on D.

## Citation

> Bombay, S. (2026). AI Model Price Changes [Data set]. {SITE}
"""
    with open(os.path.join(OUT, "README.md"), "w", encoding="utf-8") as f:
        f.write(card)
    print(f"dataset: {len(rows)} events, {len(prices)} models, {first} to {last}")
    print(f"csv rows: cuts {cuts}, rises {rises}")


if __name__ == "__main__":
    main()
