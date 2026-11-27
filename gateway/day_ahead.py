"""Single-gateway economic preview. Never submits equipment commands."""
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from math import sin, pi
from zoneinfo import ZoneInfo


def day_slots(day, zone):
    """UTC stepping preserves all 92/96/100 local settlement intervals."""
    start = datetime.combine(day, time(), zone).astimezone(timezone.utc)
    end = datetime.combine(day + timedelta(days=1), time(), zone).astimezone(timezone.utc)
    return [start + timedelta(minutes=15*i) for i in range(int((end-start).total_seconds()/900))]


def demo_plan(zone_name='Europe/Bucharest', today=None):
    zone = ZoneInfo(zone_name)
    day = (today or datetime.now(zone).date()) + timedelta(days=1)
    return _demo(day, zone_name)


@lru_cache(maxsize=32)
def _demo(day, zone_name):
    zone = ZoneInfo(zone_name)
    inputs = []
    for stamp in day_slots(day, zone):
        local = stamp.astimezone(zone)
        hour = local.hour + local.minute/60
        # Illustrative EUR/kWh settlement prices, not fetched market data.
        spot = .045 if 1 <= hour < 5 else .24 if 17 <= hour < 21 else .065 if 10 <= hour < 15 else .12
        solar = max(0, sin(pi*(hour-8)/8)) * 1.4 if 8 <= hour <= 16 else 0
        load = .25 + (.45 if 7 <= hour < 9 or 17 <= hour < 22 else 0)
        inputs.append(dict(start=stamp.isoformat(), local=local.isoformat(),
                           buy_eur_kwh=spot+.04, sell_eur_kwh=spot-.01,
                           solar_kwh=solar*.25, load_kwh=load*.25))
    return optimize(inputs, day.isoformat(), zone_name)


def optimize(inputs, day, zone_name):
    """Dynamic program on a 0.05 kWh storage lattice; fixed terminal inventory.

    Solar serves load first. Battery charging uses surplus solar before grid.
    Meter exchange is netted per interval; no simultaneous charge/discharge.
    """
    step, efficiency, limit, wear = .05, .95, 2.99, .02
    low, high, initial = 6, 54, 30  # 3 kWh, 10-90% usable, initial/final 50%
    costs, paths = {initial: 0.0}, []
    for slot in inputs:
        next_costs, parents = {}, {}
        for before, cost in costs.items():
            for after in range(low, high+1):
                delta = (after-before)*step
                charge = max(0, delta)/efficiency
                discharge = max(0, -delta)*efficiency
                if max(charge, discharge) > limit*.25+1e-9:
                    continue
                grid = slot['load_kwh']-slot['solar_kwh']+charge-discharge
                expense = max(0, grid)*slot['buy_eur_kwh']-max(0, -grid)*slot['sell_eur_kwh']
                total = cost+expense+abs(delta)*wear
                if total < next_costs.get(after, float('inf')):
                    next_costs[after] = total
                    parents[after] = (before, charge, discharge, grid, abs(delta)*wear)
        costs = next_costs
        paths.append(parents)
    state, rows = initial, []
    for slot, parents in reversed(list(zip(inputs, paths))):
        before, charge, discharge, grid, degradation = parents[state]
        surplus = max(0, slot['solar_kwh']-slot['load_kwh'])
        solar_charge = min(charge, surplus)
        rows.append(dict(slot, soc_start_pct=before*step/3*100, soc_end_pct=state*step/3*100,
                         charge_kw=charge*4, discharge_kw=discharge*4,
                         solar_charge_kwh=solar_charge, grid_charge_kwh=charge-solar_charge,
                         import_kwh=max(0, grid), export_kwh=max(0, -grid),
                         import_cost_eur=max(0, grid)*slot['buy_eur_kwh'],
                         export_value_eur=max(0, -grid)*slot['sell_eur_kwh'],
                         degradation_eur=degradation,
                         action='Solar + grid charge' if charge-solar_charge > 1e-9 and solar_charge > 0 else
                         'Grid charge' if charge-solar_charge > 1e-9 else 'Solar charge' if charge > 0 else
                         'Discharge / export' if discharge > 0 and grid < 0 else
                         'Discharge to home' if discharge > 0 else 'Hold / solar to home'))
        state = before
    rows.reverse()
    imported = sum(r['import_cost_eur'] for r in rows)
    exported = sum(r['export_value_eur'] for r in rows)
    degradation = sum(r['degradation_eur'] for r in rows)
    baseline = sum(max(0, s['load_kwh']-s['solar_kwh'])*s['buy_eur_kwh'] -
                   max(0, s['solar_kwh']-s['load_kwh'])*s['sell_eur_kwh'] for s in inputs)
    return dict(date=day, timezone=zone_name, source='Synthetic demo prices and forecasts',
                currency='EUR', executable=False, scope='single_gateway', interval_minutes=15,
                assumptions=dict(capacity_kwh=3, min_soc_pct=10, max_soc_pct=90,
                                 initial_soc_pct=50, final_soc_pct=50, max_charge_kw=limit,
                                 max_discharge_kw=limit, charge_efficiency=efficiency,
                                 discharge_efficiency=efficiency, degradation_eur_per_kwh_throughput=wear,
                                 import_adder_eur_kwh=.04, export_deduction_eur_kwh=.01),
                summary=dict(import_cost_eur=imported, export_value_eur=exported,
                             net_financial_gain_eur=exported-imported-degradation,
                             degradation_eur=degradation, baseline_cost_eur=baseline,
                             savings_vs_no_battery_eur=baseline-(imported-exported+degradation),
                             import_kwh=sum(r['import_kwh'] for r in rows),
                             export_kwh=sum(r['export_kwh'] for r in rows)), slots=rows)
