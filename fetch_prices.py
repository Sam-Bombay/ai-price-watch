#!/usr/bin/env python3
"""Snapshot the AI model price market and record every change.

Source: OpenRouter's public /api/v1/models catalogue (no key, ~470 models with real per-token prices).
Run daily. Writes:
  data/snapshot.json  full prior/current state used for diffing
  data/latest.json    compact table the public page renders
  data/changes.json   append-only log of detected price changes, new and retired models

usage: fetch_prices.py [--quiet]
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
SRC = "https://openrouter.ai/api/v1/models"
MTOK = 1_000_000


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def fetch():
    req = urllib.request.Request(SRC, headers={"User-Agent": "ai-price-watch/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["data"]


def price_per_mtok(v):
    """OpenRouter prices are USD per token as strings. -1 is the sentinel for
    'dynamic/router pricing' — report that as unknown, never as a number."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    if n <= 0:
        return None
    return round(n * MTOK, 4)


def compact(models):
    out = {}
    for m in models:
        p = m.get("pricing") or {}
        out[m["id"]] = {
            "id": m["id"],
            "name": m.get("name") or m["id"],
            "in": price_per_mtok(p.get("prompt")),
            "out": price_per_mtok(p.get("completion")),
            "ctx": m.get("context_length"),
        }
    return out


def main():
    quiet = "--quiet" in sys.argv
    os.makedirs(DATA, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prev = load(os.path.join(DATA, "snapshot.json"), {})
    changes = load(os.path.join(DATA, "changes.json"), [])
    try:
        cur = compact(fetch())
    except Exception as e:  # noqa: BLE001
        print(f"source unavailable, keeping last snapshot: {e}")
        return 0

    if not prev:  # first ever run: seed the file, nothing to diff
        note = "seeded"
    else:
        note = ""
        for mid, m in cur.items():
            old = prev.get(mid)
            if not old:
                changes.append({"date": today, "id": mid, "name": m["name"], "field": "added",
                                "from": None, "to": m["out"]})
                continue
            for field, label in (("in", "input"), ("out", "output")):
                a, b = old.get(field), m.get(field)
                if a is None or b is None or a == b:
                    continue
                pct = round((b - a) / a * 100, 1) if a else None
                changes.append({"date": today, "id": mid, "name": m["name"], "field": label,
                                "from": a, "to": b, "pct": pct})
        for mid, old in prev.items():
            if mid not in cur:
                changes.append({"date": today, "id": mid, "name": old["name"], "field": "retired",
                                "from": old.get("out"), "to": None})

    # keep the log bounded but never lose the recent tail
    changes = changes[-4000:]

    with open(os.path.join(DATA, "snapshot.json"), "w") as f:
        json.dump(cur, f, indent=0, sort_keys=True)
    with open(os.path.join(DATA, "changes.json"), "w") as f:
        json.dump(changes, f, indent=0)
    with open(os.path.join(DATA, "latest.json"), "w") as f:
        json.dump({"updated": today, "models": sorted(cur.values(), key=lambda x: (x["out"] is None, x["out"]))},
                  f, indent=0)

    if not quiet:
        today_changes = [c for c in changes if c["date"] == today]
        cuts = [c for c in today_changes if c.get("pct") is not None and c["pct"] < 0]
        print(f"models={len(cur)} changes_today={len(today_changes)} {note}".strip())
        for c in cuts[:10]:
            print(f"  {c['name'][:40]:42} {c['field']:6} {c['from']} -> {c['to']} ({c['pct']}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
