#!/usr/bin/env python3
"""Offline sales workbench. Python standard library only; never sends or uploads data.
Usage: python3 money_tools.py audit bills.csv
       python3 money_tools.py leads leads.csv --as-of 2026-10-18
CSV schemas and illustrative fixtures are at /workbench on AI Price Watch.
"""
import argparse
import csv
import datetime as dt
import json
from decimal import Decimal, InvalidOperation


def amount(value):
    try:
        n = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Invalid numeric value')
    if not n.is_finite() or n < 0:
        raise ValueError('Amounts must be finite and nonnegative')
    return n


def audit(rows):
    baseline = after = transition = Decimal(0)
    for r in rows:
        months = amount(r['period_months'])
        if months == 0:
            raise ValueError('period_months must be positive')
        baseline += amount(r['baseline_usd']) / months
        after += amount(r['replacement_usd']) / months
        transition += amount(r['one_time_usd'])
    # Charge only against the positive net aggregate; do not cherry-pick saved lines.
    net_first = baseline - after - transition
    recurring = baseline - after
    fee = max(Decimal(0), net_first) * Decimal('.30')
    return {k: str(v.quantize(Decimal('.01'))) for k, v in {
        'baseline_monthly': baseline, 'replacement_monthly': after,
        'transition_cost': transition, 'first_month_net_saving': net_first,
        'first_month_fee': fee, 'first_month_client_keeps': net_first-fee,
        'recurring_net_saving': recurring,
        'recurring_fee': max(Decimal(0), recurring)*Decimal('.30')}.items()}


def leads(rows, today):
    queue, excluded, seen = [], 0, set()
    for r in rows:
        identity = r['lead_id'].strip()
        if not identity or identity in seen:
            raise ValueError('lead_id must be nonempty and unique')
        seen.add(identity)
        date = dt.date.fromisoformat(r['last_contact'])
        age = (today-date).days
        if age < 0:
            raise ValueError('Future last_contact')
        if r['consent'].strip().lower() != 'yes' or r['status'].strip().lower() != 'open' or age < 7:
            excluded += 1
            continue
        # IDs only: no names, phone numbers, message bodies or invented personalised copy.
        queue.append({'lead_id':identity,'days_since_contact':age,
                      'next_action':'Human review of original enquiry; confirm consent and current status before one follow-up'})
    return {'queue':sorted(queue,key=lambda r:r['days_since_contact'],reverse=True),
            'excluded':excluded,'sent':0}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['audit','leads']); p.add_argument('csv')
    p.add_argument('--as-of',default=dt.date.today().isoformat())
    a=p.parse_args()
    try:
        with open(a.csv,newline='',encoding='utf-8-sig') as f:
            rows=list(csv.DictReader(f))
        if not rows: raise ValueError('CSV has no data rows')
        result=audit(rows) if a.mode=='audit' else leads(rows,dt.date.fromisoformat(a.as_of))
        print(json.dumps(result,indent=2))
    except (ValueError,KeyError,OSError) as e:
        p.error(str(e))

if __name__=='__main__': main()
