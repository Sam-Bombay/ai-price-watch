#!/usr/bin/env python3
"""Free public JSON tier of AI Price Watch.

Writes api/prices.json, api/changes.json and api/index.json from the daily pull in
tracker/data/. Stable paths, stable schema, no key. The paid tier is the change-only
diff feed plus webhook (see /dataset).
"""
import json
import os
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
API = os.path.join(ROOT, "api")
VERSION = "1"


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


def main():
    os.makedirs(API, exist_ok=True)
    latest = load("latest.json")
    changes = load("changes.json")
    events = changes if isinstance(changes, list) else changes.get("events", changes.get("changes", []))

    prices = {
        "schema": "ai-price-watch/prices",
        "version": VERSION,
        "source": "OpenRouter public model catalogue, pulled daily",
        "license": "CC-BY-4.0, attribution: ai-price-watch-beta.vercel.app",
        "updated": latest.get("updated") or time.strftime("%Y-%m-%d"),
        "count": len(latest.get("models", [])),
        "units": {"in": "USD per 1M input tokens", "out": "USD per 1M output tokens", "ctx": "tokens"},
        "models": latest.get("models", []),
    }
    with open(os.path.join(API, "prices.json"), "w", encoding="utf-8") as fh:
        json.dump(prices, fh, separators=(",", ":"))

    diff = {
        "schema": "ai-price-watch/changes",
        "version": VERSION,
        "source": "AI Price Watch change log",
        "license": "CC-BY-4.0, attribution: ai-price-watch-beta.vercel.app",
        "updated": time.strftime("%Y-%m-%d"),
        "count": len(events),
        "note": "Free tier returns the full log. The paid feed returns only the day's "
                "changes, with a stable event id and a webhook on publish.",
        "events": events,
    }
    with open(os.path.join(API, "changes.json"), "w", encoding="utf-8") as fh:
        json.dump(diff, fh, separators=(",", ":"))

    index = {
        "schema": "ai-price-watch/index",
        "version": VERSION,
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "endpoints": [
            {"path": "/api/prices.json", "what": "current price per model, USD per 1M tokens",
             "count": prices["count"]},
            {"path": "/api/changes.json", "what": "every logged price change, oldest first",
             "count": diff["count"]},
        ],
        "paid": {
            "what": "change-only diff feed, stable event ids, webhook on publish, CSV + JSON",
            "price_usd_month": 500,
            "url": "/dataset",
        },
        "contact": "Aria, assistant to Sam Bombay, Noir & Co",
    }
    with open(os.path.join(API, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=1)
    print("api: prices %d, events %d" % (prices["count"], diff["count"]))


if __name__ == "__main__":
    main()
