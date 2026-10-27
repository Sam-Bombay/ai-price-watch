---
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

Maintained by Sam Bombay / Noir & Co. Live view: https://ai-price-watch-beta.vercel.app

## What is in it

- `changes.csv` - every logged change: `date, model_id, model_name, field, price_from, price_to, pct_change`.
  `field` is `input`, `output`, `added` (new model) or `retired` (withdrawn).
  All prices are USD per 1,000,000 tokens.
- `prices.csv` - the current snapshot: input and output price and context window per model.

Coverage: **653 events** across **463 models**, 2026-10-08 to 2026-10-27.
Of 583 comparable price events, **293 are cuts and 290 are rises**.

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

> Bombay, S. (2026). AI Model Price Changes [Data set]. https://ai-price-watch-beta.vercel.app
