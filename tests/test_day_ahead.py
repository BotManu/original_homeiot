import unittest
from datetime import date
from zoneinfo import ZoneInfo

from gateway.day_ahead import day_slots, demo_plan, optimize


class DayAheadTests(unittest.TestCase):
    def test_demo_conservation_limits_and_money(self):
        plan = demo_plan(today=date(2026, 11, 27))
        self.assertEqual(plan['date'], '2026-11-28')
        self.assertEqual(len(plan['slots']), 96)
        self.assertFalse(plan['executable'])
        rows = plan['slots']
        self.assertAlmostEqual(rows[0]['soc_start_pct'], rows[-1]['soc_end_pct'])
        for s in rows:
            self.assertGreaterEqual(s['soc_end_pct'], 10-1e-8)
            self.assertLessEqual(s['soc_end_pct'], 90+1e-8)
            self.assertLessEqual(max(s['charge_kw'], s['discharge_kw']), 2.99+1e-8)
            self.assertEqual(s['charge_kw']*s['discharge_kw'], 0)
            self.assertAlmostEqual(s['solar_kwh']+s['import_kwh']+s['discharge_kw']/4,
                                   s['load_kwh']+s['export_kwh']+s['charge_kw']/4)
            self.assertAlmostEqual((s['soc_end_pct']-s['soc_start_pct'])*3/100,
                                   s['charge_kw']/4*.95-s['discharge_kw']/4/.95)
        summary = plan['summary']
        self.assertAlmostEqual(summary['net_financial_gain_eur'], sum(
            s['export_value_eur']-s['import_cost_eur']-s['degradation_eur'] for s in rows))
        self.assertGreater(summary['savings_vs_no_battery_eur'], 0)
        self.assertTrue(any(s['grid_charge_kwh'] > 0 for s in rows))
        self.assertTrue(any(s['solar_charge_kwh'] > 0 for s in rows))

    def test_dst_days(self):
        zone = ZoneInfo('Europe/Bucharest')
        self.assertEqual(len(day_slots(date(2026, 3, 29), zone)), 92)
        self.assertEqual(len(day_slots(date(2026, 10, 25), zone)), 100)

    def test_flat_price_does_not_cycle_for_profit(self):
        slots = [dict(start=str(i), local=str(i), buy_eur_kwh=.1, sell_eur_kwh=.1,
                      load_kwh=0, solar_kwh=0) for i in range(96)]
        plan = optimize(slots, '2026-11-28', 'Europe/Bucharest')
        self.assertAlmostEqual(plan['summary']['net_financial_gain_eur'], 0)
        self.assertTrue(all(s['charge_kw'] == s['discharge_kw'] == 0 for s in plan['slots']))

    def test_negative_prices_preserve_bounds(self):
        slots = [dict(start=str(i), local=str(i), buy_eur_kwh=-.1 if i < 48 else .3,
                      sell_eur_kwh=-.12 if i < 48 else .25, load_kwh=0, solar_kwh=0)
                 for i in range(96)]
        plan = optimize(slots, '2026-11-28', 'Europe/Bucharest')
        self.assertGreater(plan['summary']['net_financial_gain_eur'], 0)
        self.assertAlmostEqual(plan['slots'][-1]['soc_end_pct'], 50)


if __name__ == '__main__':
    unittest.main()
