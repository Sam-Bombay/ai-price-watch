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

    # Agent-workload pricing: an agent loop re-sends its whole history every turn, so
    # billed input grows with the square of the turn count. Anyone pricing a "chat"
    # token budget against an agent fleet gets a number an order of magnitude too low.
    # Rebuilt from the same daily pull, so the figures on /agentmeter and in
    # /api/agentworkload.json cannot drift from the log.
    try:
        import statistics
        lat = json.load(open(os.path.join(DATA, "latest.json"), encoding="utf-8"))
        ch = json.load(open(os.path.join(DATA, "changes.json"), encoding="utf-8"))
        today = lat.get("updated") or time.strftime("%Y-%m-%d")
        added = {c["id"] for c in ch if c["field"] == "added"}
        retired = {c["id"] for c in ch if c["field"] == "retired"}
        pan = {}
        for m in lat["models"]:
            if m.get("in") is None or m.get("out") is None:
                continue
            if m["id"] in added or m["id"] in retired:
                continue
            pan[m["id"]] = {"name": m["name"], "in": m["in"], "out": m["out"]}
        ASSUMP = {"turns": 20, "base_context": 6000, "added_per_turn": 1200,
                  "answer_per_turn": 800, "days": 30}

        def month_usd(v, runs):
            tin = (ASSUMP["turns"] * ASSUMP["base_context"]
                   + ASSUMP["added_per_turn"] * (ASSUMP["turns"] * (ASSUMP["turns"] - 1) // 2)) \
                * runs * ASSUMP["days"] / 1e6
            tout = ASSUMP["turns"] * ASSUMP["answer_per_turn"] * runs * ASSUMP["days"] / 1e6
            return tin, tout, tin * v["in"] + tout * v["out"]

        wl = {}
        for runs in (50, 200, 1000, 5000):
            costs = sorted(((month_usd(v, runs)[2], v) for v in pan.values()), key=lambda x: x[0])
            tin, tout, _ = month_usd(costs[0][1], runs)
            wl[str(runs)] = {
                "runs_per_day": runs,
                "billed_input_m": round(tin, 1), "billed_output_m": round(tout, 1),
                "cheapest": {"model": costs[0][1]["name"], "month_usd": round(costs[0][0], 2)},
                "median_month_usd": round(statistics.median([c[0] for c in costs]), 2),
                "p90_month_usd": round(statistics.quantiles([c[0] for c in costs], n=10)[8], 2),
                "dearest": {"model": costs[-1][1]["name"], "month_usd": round(costs[-1][0], 2)},
            }
        tin, tout, _ = month_usd(next(iter(pan.values())), 200)
        models = {}
        for v in sorted(pan.values(), key=lambda x: x["name"].lower()):
            models[v["name"]] = {"month_usd_200_runs_day": round(month_usd(v, 200)[2], 2),
                                 "in_per_m": v["in"], "out_per_m": v["out"]}
        aw = {"schema": "ai-price-watch/agent-workload", "version": VERSION,
              "as_of": today,
              "note": "Monthly USD for one fixed agent workload at list prices, no cache or "
                      "batch discount. Same panel as the daily log; models added or retired "
                      "inside the window are excluded so the figures stay comparable.",
              "assumptions": ASSUMP, "workloads": wl, "models": models}
        with open(os.path.join(DATA, "agentworkload.json"), "w", encoding="utf-8") as fh:
            json.dump(aw, fh, separators=(",", ":"))
        print("api: agent workload rebuilt for %s (%d models)" % (today, len(pan)))
    except Exception as exc:  # never let this block the price feed
        print("api: agent workload NOT rebuilt: %s" % exc)

    # Vercel treats /api as the serverless-function directory and will not serve
    # static .json from it (verified 24 Nov 2026: every /api/*.json returned 404 on
    # the vercel.app host while working on the Pages mirror). Keep a real static copy
    # under /data/api_public and let vercel.json rewrite /api/*.json onto it, so the
    # documented free tier works on both hosts.
    pub = os.path.join(DATA, "api_public")
    os.makedirs(pub, exist_ok=True)
    for name in ("prices.json", "changes.json", "index.json"):
        src = os.path.join(API, name)
        if os.path.exists(src):
            with open(src, "rb") as r, open(os.path.join(pub, name), "wb") as w:
                w.write(r.read())
    aw = os.path.join(DATA, "agentworkload.json")
    if os.path.exists(aw):
        with open(aw, "rb") as r, open(os.path.join(pub, "agentworkload.json"), "wb") as w:
            w.write(r.read())
    print("api: static copies written to data/api_public")


if __name__ == "__main__":
    main()
