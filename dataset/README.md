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

Coverage: **1132 events** across **470 models**, 2026-10-08 to 2026-11-13.
Of 981 comparable price events, **494 are cuts and 486 are rises**.

## Why it is useful

AI list prices are not stable, and they do not all move in one direction. In this log the
same model routinely falls more than 20 percent and climbs straight back, while other models
are retired without notice. Anyone modelling AI unit economics, writing about AI costs, or
auditing a vendor invoice needs the dated record rather than today's rate card.

## Put it to work

Three calculators built on this same log, no signup, no cost:

- **What one engineer's coding bill should be** — https://ai-price-watch-beta.vercel.app/seatcost — enter your per-seat AI
  spend and see the same token volume priced against today's Claude, GLM, DeepSeek and Qwen
  rates, with the tier caveat stated rather than buried. This is the page to open if your
  team's Claude Code bill was questioned this week.
- **Self-host or keep paying per token** — https://ai-price-watch-beta.vercel.app/selfhost — the break-even against published
  GPU rental, with the throughput assumption shown as a slider instead of asserted.
- **Has your bill been re-bid since the cuts?** — https://ai-price-watch-beta.vercel.app/repricing — generates the re-bid
  email from the change log, dated.

Context, 03 Nov 2026: Revolut said at AI Engineer NYC that moving most coding inference to
self-hosted GLM cut its AI coding costs roughly 90 percent, across about 2,000 engineers, and
that its own figures were about a tenth of commercial alternatives. That claim is theirs, not
measured here. What this dataset adds is the dated record needed to check whether a vendor's
price actually moved when they said it did.

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
