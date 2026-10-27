#!/usr/bin/env python3
"""Free offline qualification tools. No network, no AI calls, no sending.
Usage: review_tools.py attribution|handoff|forecast input.csv
Schemas: attribution: client,owner,usd
handoff: case_id,human_requested,human_handoff,consent_revoked,contact_continued
forecast: period,actual (consecutive monthly YYYY-MM observations, at least 6)
These tools flag review items, not legal compliance or proven savings.
"""
import argparse
import csv
import datetime
import json
from decimal import Decimal


def number(v):
    n = Decimal(v)
    if not n.is_finite() or n < 0:
        raise ValueError('Expected finite nonnegative amount')
    return n


def attribution(rows):
    totals = {}
    unowned = Decimal(0)
    for r in rows:
        client = r['client'].strip()
        if not client:
            raise ValueError('Client required')
        n = number(r['usd'])
        totals[client] = totals.get(client, Decimal(0)) + n
        if not r['owner'].strip():
            unowned += n
    return {'client_totals_usd': {k: str(v) for k, v in totals.items()},
            'unowned_usd': str(unowned), 'proven_savings_usd': '0',
            'note': 'Ownerless cost is not necessarily waste. Same-period USD exports only.'}


def flag(v):
    if v not in ('yes', 'no'):
        raise ValueError('Boolean fields require yes or no')
    return v == 'yes'


def handoff(rows):
    failures, seen = [], set()
    for r in rows:
        key = r['case_id'].strip()
        if not key or key in seen:
            raise ValueError('Unique case_id required')
        seen.add(key)
        asked, handed, revoked, continued = [flag(r[k]) for k in
            ('human_requested', 'human_handoff', 'consent_revoked', 'contact_continued')]
        reasons = []
        if asked and not handed:
            reasons.append('Human requested but no handoff recorded')
        if revoked and continued:
            reasons.append('Contact continued after consent revoked')
        if reasons:
            failures.append({'case_id': key, 'review': reasons})
    return {'review_items': failures, 'cases_checked': len(seen), 'sent': 0,
            'note': 'Manual annotation required. Not an automated transcript judgement or legal certification.'}


def forecast(rows):
    if len(rows) < 6:
        raise ValueError('Need at least 6 consecutive monthly observations')
    dates = [datetime.datetime.strptime(r['period'], '%Y-%m') for r in rows]
    indices = [d.year * 12 + d.month for d in dates]
    if any(b-a != 1 for a, b in zip(indices, indices[1:])):
        raise ValueError('Periods must be consecutive, unique and ascending')
    y = [number(r['actual']) for r in rows]
    errors = []
    for i in range(3, len(y)):
        errors.append(abs(y[i] - sum(y[i-3:i], Decimal(0)) / 3))
    return {'backtest_points': len(errors), 'rolling_3_month_mae': str(sum(errors)/len(errors)),
            'next_month_baseline': str(sum(y[-3:])/3),
            'note': 'Rolling-origin baseline uses past data only. Not Timestral; no AI accuracy claim. Requires business validation.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['attribution', 'handoff', 'forecast'])
    p.add_argument('csv')
    a = p.parse_args()
    with open(a.csv, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        p.error('No data rows')
    print(json.dumps(globals()[a.mode](rows), indent=2))
