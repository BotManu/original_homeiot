# Single-gateway day-ahead financial planning

## Live trial deployed: 28 November 2026

The Olinuxino gateway now runs a **single-day live grid-charging trial** using
Energy-Charts RO day-ahead prices. Both deployed dashboards read the gateway's
actual dated plan, not synthetic PV/load forecasts. The cloud uses a private
authenticated, read-only gateway connection and fails visibly without replacing
an unavailable live plan with demo data. The older `first-home` site retains its
separately labeled demo.

The existing qualified operating ceiling is **1000 W**, not the 2990 W owner
ceiling. GRID_EXPORT, FORCED_DISCHARGE and TARIFF_OPTIMIZATION remain explicitly
unsupported by the native controller. No qualification flags, native control
code, reserve protections or write limits were changed for this trial.

The existing night planner owns execution through its usual <=180-second native
leases. Within 02:00-05:00 Europe/Bucharest it permits only the cheapest selected
15-minute intervals, ending every lease no later than its interval boundary.
Manual override, fresh qualification, target SoC, hardware fallback and the
05:00 end remain enforced. Outside the selected intervals, existing native
solar/self-consumption behavior continues. There is no forced export dispatch.

Initial snapshot: 50% SoC, 3 kWh estimated capacity, 90% target, 95% assumed
charging efficiency, a conservative 90% power-delivery allowance. Six slots
were selected, 03:30-05:00, with a maximum scheduled charging spot budget of
EUR 0.29709 before fees/taxes. At the first qualified tick in the night window,
the slot selection is recalculated from actual SoC and locked. The target is
not guaranteed if SoC/capacity differs, charging pauses or qualification fails.
The dated policy expires after 28 November; normal existing night scheduling
then resumes. Reload the dashboard to change the displayed delivery date.

The provider query uses explicit Unix timestamps covering local midnight to
midnight, converts EUR/MWh to EUR/kWh, and validates all 96 quarter hours for
this day. Prices are fetched and persisted when preparing the trial, outside
the physical control loop. No API key is required for this provider.
API contract: https://api.energy-charts.info/openapi.json
RO data is designated private/internal use by the provider; the trial remains
inside the existing private VPN dashboards.

Real grid observations accumulate daily import/export kWh and **indicative
wholesale spot values**, with sampling coverage and skipped gaps. Samples are
left-held for at most 15 seconds and split at price boundaries. These are not
supplier bills, proven financial gain, or measured battery savings. Supplier
import/export tariffs are still unconfigured; fees, tax, wear and settlement
rules are excluded. Unobserved startup time and gaps are not invented.

Runtime files under the gateway's private configuration directory:

- `day-ahead-live.json`: dated prices, planned slots and the window-start lock.
- `day-ahead-meter.json`: observed energy/spot totals and sampling coverage.
- `growatt-night-status.json`: existing planner's latest execution state.

Set `enabled` to false in `day-ahead-live.json` to restore ordinary night-window
scheduling. Pause the existing night plan to stop automatic grid charging;
manual cancellation and the native lease expiry path remain available.

Deployment retained gateway source at
`/root/originalhome-pre-live-prices-20261128.tar.gz` and the previous cloud image
as `originalhome/cloud:pre-strategy-20261127-220229`. Only the local Python gateway
and cloud app were restarted; OpenEMS remained running. Deployed checks confirmed
96 live price intervals, a qualified controller, matching cloud/gateway plans,
advancing observed energy totals and live cloud telemetry. All 44 regression
tests passed, including the six new scheduler/accounting checks; 19 relevant
tests also passed directly on the Olinuxino before activation.

## Historical demo and wider integration design

Implemented first slice: a read-only demo in both local and cloud dashboards.
Community aggregation is deferred. No plan is submitted to OpenEMS, and the
existing nightly schedule is unchanged.

## Tomorrow demo: 28 November 2026, Europe/Bucharest

96 quarter-hour intervals use synthetic prices, PV and household demand.
The demo rolls forward to the next site-local date on page load.

| Daily field | Demo estimate |
| --- | ---: |
| Imported energy cost | EUR 0.7670 (5.243 kWh) |
| Exported energy value | EUR 0.1898 (2.771 kWh) |
| Net financial gain | EUR -0.7512 |
| Battery wear allowance | EUR 0.1740 |
| Savings against identical solar/load without a battery | EUR 0.3477 |

Net gain = export value - import cost - battery wear. A negative number is a
remaining household energy cost, not evidence that the battery strategy loses
money relative to the baseline. Baseline daily cost is EUR 1.0989.
These are forecasts, not measured daily totals or supplier settlement amounts.

## Strategy and assumptions

Balance PV, household load, battery and net grid exchange every 15 minutes.
Serve load with solar first. Charge from surplus solar before using the grid.
Use grid charging when its future avoided-import or export value exceeds purchase
cost, conversion losses and wear. Preserve solar headroom when worthwhile.
Discharge to load or export when economically preferable, rather than exporting
simply because prices are cheap. Negative buy prices are supported.

The demo uses dynamic programming on 0.05 kWh battery states; the result is the
lowest forecast cost on that discrete state grid. It is not a continuous optimum.
It models 3 kWh nominal capacity, 10-90% SoC (2.4 kWh usable), 50% initial and
terminal SoC, 95% charge and discharge efficiency (90.25% round trip), and
EUR 0.02 wear per kWh of internal charge/discharge throughput. Equal initial and
terminal charge prevents monetizing initial stored energy as recurring profit.

Charge/discharge are mutually exclusive and capped at 2.99 kW AC, or 0.7475 kWh
per quarter hour. The same discharge cap is an assumption pending qualification.
At full power, charging the usable 2.4 kWh range needs about 51 minutes with losses;
the discrete quarter-hour plan can spread this over multiple slots.
The physical qualified operating cap remains 1 kW. Plans must use the actual
qualified caps before any future execution.

Synthetic spot prices: EUR 0.045/kWh at 01:00-05:00, 0.065 at 10:00-15:00,
0.240 at 17:00-21:00, otherwise 0.120. Import adds EUR 0.040/kWh;
export deducts EUR 0.010/kWh. These are illustrative, not a Romanian tariff.
The PV forecast is AC-equivalent energy; existing DC PV telemetry is not a
direct forecast input. Household demand includes morning/evening peaks.

The resulting schedule uses cheap night charging, morning discharge, solar
charging during daylight, evening peak discharge, and restores terminal charge.
The dashboards expose every interval, prices, PV/load, action, battery power,
ending SoC and grid import/export. The JSON adds the source split of charging
and interval financial contributions.

## Live API integration strategy (next slice)

Use ENTSO-E Transparency day-ahead prices for the gateway's configured bidding
zone. Its official extraction guide identifies day-ahead prices as document A44:
https://transparency.entsoe.eu/content/static_content/download?path=%2FStatic+content%2Fweb+api%2FIG-for-TP-data-extraction-process.pdf

1. Configure an ENTSO-E API token server-side and verify the Romanian bidding-zone
   identifier against the provider. Query tomorrow's local-midnight boundaries
   converted to UTC with `documentType=A44`, `in_Domain`, `out_Domain`,
   `periodStart`, `periodEnd`, and `securityToken`. Confirm the daily auction
   selection and returned currency, units and resolution against a real response.
2. Parse positions and period timestamps, convert EUR/MWh to EUR/kWh, require
   unique contiguous 15-minute intervals covering the full local day. Expect
   92/96/100 intervals on daylight-saving/normal days. Reject incomplete or
   unexpected-resolution data; do not silently interpolate market prices.
3. Fetch after next-day prices are published; retry missing data with bounded
   backoff. Cache by provider, zone, delivery date and revision. Store retrieval
   time and source separately from the delivery timestamps. A failed fetch must
   display 'prices unavailable' and must never relabel synthetic data as live.
   Do not fetch prices on the five-second telemetry polling loop.
4. Apply separate supplier import and export settlement formulas, network charges,
   taxes and currency conversion. Confirm whether battery energy bought from the
   grid may be exported and how it is paid. Support export-disabled operation and
   separate site connection limits before real dispatch.
5. Replace synthetic PV/load with site forecasts, including AC conversion and
   confidence estimates. Use measured fresh SoC and verified usable capacity,
   reserve, battery/inverter power limits and tariff configuration. Optimize
   against a solar self-consumption baseline as well as the no-battery baseline.
6. Persist a versioned plan and forecasts. Replan remaining intervals as forecasts
   change; compare measured daily settlement values with predicted values.
   Any later execution must go through the local OpenEMS allowlisted control
   path, honor manual override and the existing night-schedule ownership, and
   enforce freshness, expiry, qualified limits and observed feedback.

The current APIs deliberately return only labeled demo plans:
`GET /api/energy/plan` locally and authenticated, membership-scoped
`GET /api/sites/{site_id}/plan` in the cloud. No live price connection is enabled.
The three daily financial fields are in `summary`; all interval data is in `slots`.

## Verification

Tests cover energy conservation, SoC transition losses/reserve/terminal inventory,
charge/discharge limits, financial reconciliation, flat and negative price cases,
DST interval counts, local HTTP access and cloud membership isolation.
Windows Python needs IANA timezone data (`pip install tzdata`); Linux deployments
normally obtain it from their system timezone database.
