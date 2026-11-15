# PoC verification — 15 November 2026

Real host: `originalpocserver`, Tailscale `100.122.80.43`.
Real gateway: `original-volt-gateway`, Tailscale `100.65.109.74`.

## Verified

| Check | Result |
| --- | --- |
| Full repository regression suite on development computer | 20 tests passed |
| Cloud tests in deployed Linux/Python image | 7 tests passed |
| Deployed dashboard JavaScript | Node 22 syntax check passed |
| Health/login/site/history/CSV API over VPN | HTTP 200 with owner login |
| Unauthenticated site API | HTTP 401 |
| Cross-site detail/history/export access | HTTP 404 in authorization tests |
| Missing/stale/nonfinite/invalid equipment data | Rejected in contract tests |
| Genuine zero-valued solar versus missing solar | Zero accepted; null rejected |
| Source | Fresh real `growatt0` measurements through native Backend/ingress |
| Application restart | Existing session, persisted sample and live source recovered |
| PostgreSQL uniqueness | 80 samples / 80 distinct IDs; no duplicate site/observation pairs at check |
| Local gateway during recovery exercise | Both user services active; fresh equipment samples advanced; controls disabled |
| Startup ordering | `originalhome-poc.service` enabled and active |

The application-restart verification retained 61 historical samples at that
point and observed a fresh source age of 2,898 ms. Subsequent samples continued
to accumulate. All five cloud containers were running at final service check;
application and PostgreSQL health checks were healthy.

## Outage and reconnect evidence

Stopped **only the new cloud ingress** briefly, then restored it in a
`finally` block. The application retained its last sample and reported stale
measurements after 25 seconds. No fabricated replacement values were used.

An initial 100-second test deadline was too short: the native connector's
unchanged zero-valued solar channel lacked a baseline after reconnection.
Readings later recovered at its default periodic full snapshot. The recorded
gap from source timestamp `1794773432844` to `1794773732861` is 300,017 ms and
remains explicit in history. A separate cloud Backend restart produced another
explicit gap. The application subscription watchdog now retries empty/stale
sessions; the native full-baseline delay remains an identified pilot gate.

This proves eventual native reconnection and honest gap/stale reporting for
the exercised outage. It does not prove complete offline history replay.

## Not yet verified or implemented

- Browser rendering/interaction QA: the browser-access host was unavailable.
  Assets and APIs were checked, and JavaScript syntax passed, but there is no
  screenshot-based visual acceptance.
- Full physical host/gateway reboot, power failure and long field soak.
- Native timedata store and deduplicated offline history replay.
- Off-host backups and restoration on a clean server.
- Production OIDC/MFA, enrollment, rotation/revocation and gateway replacement.
- Hardware daylight/sign/identity qualification, writable energy integration,
  automatic local strategy, supervisory commands and VPP.

The system is a private engineering monitoring PoC. It is not a completed
production release, qualified controller or VPP pilot.
