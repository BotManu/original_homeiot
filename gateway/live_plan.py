"""Dated, price-ranked grid charging through the existing qualified night planner.

No export/discharge commands. Prices are indicative wholesale values, not bills.
"""
from datetime import datetime, timedelta
import json
from math import ceil, isfinite
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from .day_ahead import day_slots
from .energy_control import atomic_private_write, controls_ready, status

NAME = 'day-ahead-live.json'


def read(folder):
    path = Path(folder)/NAME
    if not path.exists():
        return None
    if path.stat().st_size > 250000:
        raise ValueError('Oversized live plan')
    return json.loads(path.read_text())


def prices(day, zone_name='Europe/Bucharest'):
    zone = ZoneInfo(zone_name)
    expected = day_slots(day, zone)
    # Explicit epoch boundaries avoid the provider's default date/timezone range.
    end = expected[-1] + timedelta(minutes=15)
    url = 'https://api.energy-charts.info/price?' + urlencode(dict(
        bzn='RO', start=int(expected[0].timestamp()), end=int(end.timestamp())))
    with urlopen(url, timeout=20) as response:
        payload = response.read(250001)
    if len(payload) > 250000:
        raise ValueError('Oversized price response')
    data = json.loads(payload)
    if data.get('unit') != 'EUR / MWh' or data.get('deprecated') is not False:
        raise ValueError('Unexpected price units or deprecated data')
    stamps, amounts = data.get('unix_seconds', []), data.get('price', [])
    if len(stamps) != len(amounts):
        raise ValueError('Mismatched prices')
    lookup = {}
    for stamp, amount in zip(stamps, amounts):
        if type(stamp) is not int or type(amount) not in (int, float) or not isfinite(amount):
            raise ValueError('Invalid price')
        if stamp in lookup:
            raise ValueError('Duplicate interval')
        lookup[stamp] = amount/1000
    wanted = {int(s.timestamp()) for s in expected}
    # API may include the exclusive end; never accept missing interior intervals.
    if not wanted <= lookup.keys():
        raise ValueError('Incomplete next-day quarter-hour prices')
    return [dict(start_ms=int(s.timestamp()*1000), local=s.astimezone(zone).isoformat(),
                 spot_eur_kwh=lookup[int(s.timestamp())]) for s in expected], url, data.get('license_info', '')


def rank(plan, soc):
    """Budget with conservative 0.9 kW delivered power, 95% charge efficiency."""
    if type(soc) not in (int, float) or not isfinite(soc) or not 0 <= soc <= 100:
        raise ValueError('Fresh SoC required')
    budget = max(0, plan['target_soc']-soc)/100*plan['capacity_kwh']/.95
    count = ceil(budget/(plan['charge_w']/1000*.90*.25)-1e-9)
    eligible = [s for s in plan['slots'] if plan['window_start'] <= s['local'][11:16] < plan['window_end']]
    selected = {s['start_ms'] for s in sorted(eligible, key=lambda s:(s['spot_eur_kwh'],s['start_ms']))[:count]}
    for s in plan['slots']:
        s['selected'] = s['start_ms'] in selected
    plan.update(planning_soc=soc, selected_intervals=len(selected), required_grid_kwh=budget,
                charge_budget_spot_eur=sum(s['spot_eur_kwh']*plan['charge_w']/1000*.25 for s in eligible if s['selected']),
                target_energy_feasible=budget <= len(eligible)*plan['charge_w']/1000*.90*.25+1e-9)


def prepare(folder, day, night):
    current = status(folder)
    if not controls_ready(current) or current.get('qualification', {}).get('grid_charging_verified') is not True:
        raise ValueError('Fresh qualified grid-charging controller required')
    if night['charge_w'] > current['max_charge_w']:
        raise ValueError('Night schedule exceeds qualified operating limit')
    slots, url, license_info = prices(day, night['timezone'])
    plan = dict(schema_version=1, enabled=True, date=day.isoformat(), timezone=night['timezone'],
                source='Energy-Charts live RO day-ahead prices', currency='EUR',
                mode='live_grid_charging', charge_w=night['charge_w'], target_soc=night['target_soc'],
                capacity_kwh=3, window_start=night['start'], window_end=night['end'],
                created_ms=int(datetime.now().timestamp()*1000), locked=False,
                price_url=url, license_info=license_info, slots=slots,
                export_dispatch_enabled=False, supplier_tariff_configured=False,
                note='Single-day trial. Price-ranked charging within the existing night window. '
                     'Solar/self-consumption remains native. Wholesale values exclude supplier fees and taxes. '
                     '3 kWh capacity and 95% efficiency are estimates. No forced export or discharge.')
    rank(plan, current['battery_soc'])
    atomic_private_write(Path(folder)/NAME, plan)
    return plan


def decision(folder, now, current, night):
    """None means the normal night plan; a dated trial fails closed if invalid."""
    plan = read(folder)
    if not plan or not plan.get('enabled') or plan.get('date') != now.date().isoformat():
        return None
    if (plan['charge_w'] != night['charge_w'] or plan['target_soc'] != night['target_soc']
            or plan['window_start'] != night['start'] or plan['window_end'] != night['end']):
        return dict(charge=False, reason='live_plan_configuration_changed')
    if not controls_ready(current, now_ms=int(now.timestamp()*1000)):
        return dict(charge=False, reason='live_plan_waiting_for_fresh_qualification')
    # Once at the night-window start, use actual SoC rather than yesterday's SoC.
    if not plan.get('locked'):
        rank(plan, current['battery_soc'])
        plan['locked'] = True
        plan['locked_ms'] = int(now.timestamp()*1000)
        atomic_private_write(Path(folder)/NAME, plan)
    stamp = int(now.timestamp()*1000)
    slot = next((s for s in plan['slots'] if s['start_ms'] <= stamp < s['start_ms']+900000), None)
    if slot is None:
        return dict(charge=False, reason='live_plan_interval_missing')
    return dict(charge=slot['selected'], reason='live_plan_price_hold',
                end_ms=slot['start_ms']+900000)


def view(folder):
    plan = read(folder)
    if plan is None:
        return None
    result = dict(plan)
    meter = Path(folder)/'day-ahead-meter.json'
    result['meter'] = json.loads(meter.read_text()) if meter.exists() else None
    if result['meter'] and result['meter'].get('date') != plan['date']:
        result['meter'] = None
    current = status(folder)
    result['controller'] = {k:current.get(k) for k in ('status','reason','max_charge_w','battery_soc','run_active','observed_ms')}
    result['control_ready'] = controls_ready(current)
    return result


def record(folder, previous, sample):
    """Left-held grid samples valued at real spot prices; gaps are not invented."""
    plan = read(folder)
    if not plan or not plan.get('enabled'):
        return
    path = Path(folder)/'day-ahead-meter.json'
    meter = json.loads(path.read_text()) if path.exists() else {}
    if meter.get('date') != plan['date']:
        meter = dict(date=plan['date'], covered_seconds=0, import_kwh=0, export_kwh=0,
                     import_spot_eur=0, export_spot_eur=0, skipped_gap_seconds=0)
    if previous:
        left, right = previous['ts'], sample['ts']
        if 0 < right-left <= 15000:
            for s in plan['slots']:
                duration = max(0, min(right, s['start_ms']+900000)-max(left, s['start_ms']))/1000
                if duration:
                    grid = previous['values']['grid_w']
                    imported, exported = max(0,grid)*duration/3600000, max(0,-grid)*duration/3600000
                    meter['import_kwh'] += imported
                    meter['export_kwh'] += exported
                    meter['import_spot_eur'] += imported*s['spot_eur_kwh']
                    meter['export_spot_eur'] += exported*s['spot_eur_kwh']
                    meter['covered_seconds'] += duration
        elif right > left:
            start, end = plan['slots'][0]['start_ms'], plan['slots'][-1]['start_ms']+900000
            meter['skipped_gap_seconds'] += max(0,min(right,end)-max(left,start))/1000
    meter['last_observed_ms'] = sample['ts']
    meter['net_spot_eur'] = meter['export_spot_eur']-meter['import_spot_eur']
    atomic_private_write(path, meter)
