#!/usr/bin/env python3
"""Fetch the real provider routing for every priced model in today's catalogue.

Source: OpenRouter's public per-model endpoints API,
  https://openrouter.ai/api/v1/models/<author>/<slug>/endpoints
which returns the providers that actually serve that model, with per-provider
prices and uptime. Nothing here is inferred; a model with no endpoints in the
response is recorded as having no readable route rather than assumed clean.

Output: data/routes.json  {"fetched": iso, "models": {id: [ {provider, tag, in, out, uptime} ]}}
"""
import json, os, datetime, urllib.request, concurrent.futures as cf

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
UA = {"User-Agent": "ai-price-watch/1.0 (price log; contact sambombayoffice@gmail.com)"}


def get(url, tries=3):
    for i in range(tries):
        try:
            r = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(r, timeout=30) as f:
                return json.load(f)
        except Exception as e:
            if i == tries - 1:
                return {"__error__": str(e)}
    return {}


def routes_for(mid):
    d = get("https://openrouter.ai/api/v1/models/%s/endpoints" % mid)
    if "__error__" in d:
        return mid, None, d["__error__"]
    eps = (d.get("data") or {}).get("endpoints") or []
    out = []
    for e in eps:
        p = e.get("pricing") or {}
        def m(k):
            try:
                return round(float(p.get(k)) * 1_000_000, 4)
            except (TypeError, ValueError):
                return None
        out.append({
            "provider": e.get("provider_name"),
            "tag": e.get("tag"),
            "in": m("prompt"),
            "out": m("completion"),
            "uptime": e.get("uptime_last_30m"),
            "ctx": e.get("context_length"),
        })
    return mid, out, None


def main():
    latest = json.load(open(os.path.join(DATA, "latest.json")))
    ids = [m["id"] for m in latest["models"] if m.get("in") is not None]
    print("models to map:", len(ids))
    models, errs = {}, 0
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for mid, out, err in ex.map(routes_for, ids):
            if out is None:
                errs += 1
                continue
            models[mid] = out
    doc = {"fetched": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "source": "https://openrouter.ai/api/v1/models/<id>/endpoints",
           "models": models}
    json.dump(doc, open(os.path.join(DATA, "routes.json"), "w"), separators=(",", ":"))
    n_prov = len({p["provider"] for v in models.values() for p in v})
    print("mapped %d models, %d distinct providers, %d errors" % (len(models), n_prov, errs))


if __name__ == "__main__":
    main()
