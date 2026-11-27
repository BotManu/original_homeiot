const el = id => document.getElementById(id);
let siteId = null, timezone = 'Europe/Bucharest', timer, requestVersion = 0;
const power = value => value == null ? '—' : `${(value / 1000).toFixed(2)} kW`;
const localTime = ts => new Date(ts).toLocaleTimeString([], {timeZone: timezone, hour: '2-digit', minute: '2-digit'});
async function api(path, options = {}) {
  const response = await fetch(path, {...options, signal: AbortSignal.timeout(12000)});
  if (response.status === 401) { showLogin(); throw Error('Please sign in.'); }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw Error(typeof body.detail === 'string' ? body.detail : 'Request failed. Please try again.');
  }
  return response;
}
function showLogin() {
  clearTimeout(timer); requestVersion++;
  el('app').hidden = true; el('login-screen').hidden = false;
}
el('login-form').addEventListener('submit', async event => {
  event.preventDefault(); el('login-error').textContent = '';
  const button = event.target.querySelector('button'); button.disabled = true;
  try {
    await api('/api/login', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username: el('username').value, password: el('password').value})});
    el('password').value = ''; await start();
  } catch (error) { el('login-error').textContent = error.message; }
  finally { button.disabled = false; }
});
el('logout').addEventListener('click', async () => {
  try { await api('/api/logout', {method:'POST'}); showLogin(); }
  catch (error) { el('network-error').hidden = false; el('network-error').textContent = error.message; }
});
function render(site) {
  timezone = site.timezone;
  el('site-name').textContent = site.name;
  el('site-meta').textContent = `${timezone} · Growatt SPH6000`;
  el('edge-id').textContent = site.edge_id;
  const live = site.status === 'live';
  el('status').textContent = live ? 'Live equipment' : site.latest ? 'Stale measurements' : 'Awaiting gateway';
  el('status').classList.toggle('live', live);
  el('gateway-state').textContent = site.connection.replaceAll('_', ' ');
  el('gateway-state').classList.toggle('live', live);
  el('notice').classList.toggle('warning', !!site.latest && !live);
  el('notice').textContent = live
    ? 'Reading equipment through OpenEMS. Monitoring only; daylight power and battery signs still need qualification.'
    : site.latest ? 'Equipment readings are unavailable or stale. Values below are the last recorded measurements; physical state is unconfirmed.'
    : 'Waiting for the first gateway connection. Measurements will appear when equipment data arrives.';
  const v = site.latest?.values;
  for (const [id, key] of [['solar','solar_w'],['load','load_w'],['grid','grid_w']]) el(id).textContent = power(v?.[key]);
  el('soc').textContent = v ? `${v.battery_soc}%` : '—';
  el('grid-detail').textContent = v ? v.grid_w > 0 ? 'Importing from grid' : v.grid_w < 0 ? 'Exporting to grid' : 'Balanced' : 'Import + / export −';
  el('battery-detail').textContent = v ? `${v.battery_w < 0 ? 'Charging' : v.battery_w > 0 ? 'Discharging' : 'Idle'} · ${power(Math.abs(v.battery_w))}` : 'No measurements yet';
  el('updated').textContent = site.latest ? `${live ? 'Observed' : 'Last observed'} ${localTime(site.latest.observed_ms)} · ${Math.round(site.observation_age_ms / 1000)}s ago` : 'No measurements yet';
  el('clock').textContent = new Date().toLocaleDateString([], {timeZone: timezone, day:'numeric', month:'short', year:'numeric'});
}
function draw(data) {
  const chart = el('chart'); chart.replaceChildren();
  const rows = data.samples;
  el('chart-empty').hidden = rows.length > 0;
  const ns = 'http://www.w3.org/2000/svg';
  function path(d, stroke, width=1) {
    const node = document.createElementNS(ns,'path'); node.setAttribute('d',d);
    node.setAttribute('stroke',stroke); node.setAttribute('stroke-width',width); node.setAttribute('fill','none'); chart.append(node);
  }
  for (let n=0;n<5;n++) path(`M 0 ${15+n*46} H 960`,'#edf1e9');
  el('chart-start').textContent = rows.length ? localTime(rows[0].observed_ms) : '—';
  el('chart-end').textContent = rows.length ? localTime(rows.at(-1).observed_ms) : '—';
  el('chart-note').textContent = data.truncated ? 'Showing latest 2,000 samples. Choose a shorter range.' : 'Gaps stay visible. No estimated energy totals.';
  if (!rows.length) return;
  const keys = [['solar_w','#c6ad61'],['load_w','#4f8068'],['grid_w','#8fabc0']];
  const min = Math.min(0,...rows.map(r=>r.values.grid_w));
  const max = Math.max(1000,...rows.flatMap(r=>keys.map(([key])=>r.values[key])));
  const from = rows[0].observed_ms, span = Math.max(1,rows.at(-1).observed_ms-from);
  for (const [value,y] of [[max,12],[min,216]]) {
    const label = document.createElementNS(ns,'text');
    label.setAttribute('x','5'); label.setAttribute('y',String(y));
    label.setAttribute('fill','#8d9986'); label.setAttribute('font-size','10');
    label.textContent = power(value); chart.append(label);
  }
  for (const [key,color] of keys) {
    let previous = null, d = '';
    for (const row of rows) {
      const x = (row.observed_ms-from)/span*960, y = 199-(row.values[key]-min)/(max-min)*184;
      d += `${previous === null || row.observed_ms-previous > data.gap_threshold_ms ? 'M' : 'L'} ${x} ${y} `;
      previous = row.observed_ms;
    }
    path(d,color,2.5);
  }
}
async function refresh() {
  clearTimeout(timer);
  const version = ++requestVersion, selected = siteId;
  try {
    const [site,data] = await Promise.all([
      api(`/api/sites/${encodeURIComponent(selected)}`).then(r=>r.json()),
      api(`/api/sites/${encodeURIComponent(selected)}/history?hours=${el('hours').value}`).then(r=>r.json())]);
    if (version !== requestVersion) return;
    render(site); draw(data); el('network-error').hidden = true;
  } catch {
    if (version !== requestVersion) return;
    el('network-error').hidden = false;
    el('status').textContent = 'Cloud unreachable'; el('status').classList.remove('live');
  } finally {
    if (version === requestVersion && !el('app').hidden) timer = setTimeout(refresh,5000);
  }
}
async function start() {
  const data = await api('/api/sites').then(r=>r.json());
  el('site-select').replaceChildren();
  for (const site of data.sites) {
    const option = document.createElement('option'); option.value = site.id; option.textContent = site.name;
    el('site-select').append(option);
  }
  siteId = data.sites[0]?.id;
  el('login-screen').hidden = true; el('app').hidden = false;
  if (siteId) { loadDayPlan(`/api/sites/${encodeURIComponent(siteId)}/plan`); await refresh(); }
  else { el('notice').textContent = 'No sites are assigned to this account.'; el('export').disabled = true; }
}
el('site-select').addEventListener('change', () => {siteId = el('site-select').value; loadDayPlan(`/api/sites/${encodeURIComponent(siteId)}/plan`); refresh();});
el('hours').addEventListener('change',refresh);
el('export').addEventListener('click', async () => {
  const button = el('export'); button.disabled = true;
  try {
    const response = await api(`/api/sites/${encodeURIComponent(siteId)}/export.csv?hours=${el('hours').value}`);
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a'); link.href = url; link.download = 'originalhome-energy.csv'; link.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  } catch(error) {el('network-error').hidden = false; el('network-error').textContent = error.message;}
  finally {button.disabled = false;}
});
start().catch(error => {if (error.message !== 'Please sign in.') el('login-error').textContent = error.message;});


const defaultPlanColumns = document.getElementById('plan-columns').innerHTML;
const defaultPlanAssumptions = document.getElementById('plan-assumptions').textContent;
const defaultPlanDisclaimer = document.getElementById('plan-disclaimer').textContent;
let dayPlanVersion = 0, dayPlanTimer;
async function loadDayPlan(path) {
  const version = ++dayPlanVersion; clearTimeout(dayPlanTimer);
  const meta = document.getElementById('plan-meta');
  for (const id of ['plan-import','plan-export','plan-net']) document.getElementById(id).textContent = '--';
  for (const id of ['plan-import-energy','plan-export-energy','plan-savings']) document.getElementById(id).textContent = '';
  document.getElementById('plan-slots').replaceChildren();
  try {
    const response = await fetch(path, {signal: AbortSignal.timeout(12000)});
    if (!response.ok) throw Error('unavailable');
    const plan = await response.json();
    if (version !== dayPlanVersion) return;
    if (plan.mode === 'live_grid_charging') { renderLivePlan(plan); dayPlanTimer = setTimeout(() => loadDayPlan(path), 60000); return; }
    document.getElementById('plan-badge').textContent = 'Demo';
    document.getElementById('plan-columns').innerHTML = defaultPlanColumns;
    document.getElementById('plan-assumptions').textContent = defaultPlanAssumptions;
    document.getElementById('plan-disclaimer').textContent = defaultPlanDisclaimer;
    const labels = document.querySelectorAll('#day-plan .plan-metrics article > span');
    labels[0].textContent='Daily imported energy cost'; labels[1].textContent='Daily exported energy value'; labels[2].textContent='Net financial gain';
    document.querySelector('#plan-net + small').textContent='Export minus import minus battery wear';
    const money = n => new Intl.NumberFormat(undefined, {style:'currency',currency:plan.currency}).format(n);
    const s = plan.summary;
    meta.textContent = `${plan.date} | ${plan.timezone} | ${plan.slots.length} intervals | ${plan.source} | One gateway`;
    document.getElementById('plan-import').textContent = money(s.import_cost_eur);
    document.getElementById('plan-export').textContent = money(s.export_value_eur);
    document.getElementById('plan-net').textContent = money(s.net_financial_gain_eur);
    document.getElementById('plan-import-energy').textContent = `${s.import_kwh.toFixed(2)} kWh imported`;
    document.getElementById('plan-export-energy').textContent = `${s.export_kwh.toFixed(2)} kWh exported`;
    document.getElementById('plan-savings').textContent = `Battery savings versus the same solar/home forecast without a battery: ${money(s.savings_vs_no_battery_eur)}. Battery wear allowance: ${money(s.degradation_eur)}. A negative net means the home still has a net daily energy cost.`;
    for (const slot of plan.slots) {
      const tr = document.createElement('tr');
      const values = [slot.local.slice(11,16)+' '+slot.local.slice(-6), `${slot.buy_eur_kwh.toFixed(3)} / ${slot.sell_eur_kwh.toFixed(3)}`, `${slot.solar_kwh.toFixed(3)} / ${slot.load_kwh.toFixed(3)}`,slot.action,`${slot.charge_kw.toFixed(2)} / ${slot.discharge_kw.toFixed(2)}`,`${slot.soc_end_pct.toFixed(1)}%`,`${slot.import_kwh.toFixed(3)} / ${slot.export_kwh.toFixed(3)}`];
      for (const value of values) { const td = document.createElement('td'); td.textContent = value; tr.append(td); }
      document.getElementById('plan-slots').append(tr);
    }
  } catch { if (version === dayPlanVersion) { document.getElementById('plan-badge').textContent = 'Unavailable'; meta.textContent = 'Plan unavailable. No demo data is substituted for a live gateway.'; } }
}

function renderLivePlan(plan) {
  const money = value => value == null ? '--' : new Intl.NumberFormat(undefined,{style:'currency',currency:'EUR'}).format(value);
  document.getElementById('plan-badge').textContent = 'Live charging / real prices';
  document.getElementById('plan-meta').textContent = `${plan.date} | ${plan.timezone} | ${plan.source} | ${plan.control_ready ? 'Qualified controller ready' : 'Controller unavailable: dispatch blocked'} | Single-day trial`;
  const meter = plan.meter, measured = meter && meter.covered_seconds > 0;
  const labels = document.querySelectorAll('#day-plan .plan-metrics article > span');
  labels[0].textContent='Imported energy spot value'; labels[1].textContent='Exported energy spot value'; labels[2].textContent='Net spot value';
  document.getElementById('plan-import').textContent=money(measured ? meter.import_spot_eur : null);
  document.getElementById('plan-export').textContent=money(measured ? meter.export_spot_eur : null);
  document.getElementById('plan-net').textContent=money(measured ? meter.net_spot_eur : null);
  document.getElementById('plan-import-energy').textContent=measured ? `${meter.import_kwh.toFixed(3)} kWh observed` : 'Awaiting trial-day measurements';
  document.getElementById('plan-export-energy').textContent=measured ? `${meter.export_kwh.toFixed(3)} kWh observed` : 'Export dispatch unsupported';
  document.querySelector('#plan-net + small').textContent='Observed export minus import at wholesale prices';
  document.getElementById('plan-savings').textContent=`${plan.selected_intervals} selected charging intervals. Maximum scheduled grid charge budget at spot prices: ${money(plan.charge_budget_spot_eur)}. Supplier financial gain unavailable until import/export tariffs are configured. ${measured ? `Observed coverage: ${(meter.covered_seconds/3600).toFixed(2)} hours; skipped gaps: ${meter.skipped_gap_seconds.toFixed(0)} seconds.` : ''}`;
  document.getElementById('plan-assumptions').textContent=`Live charging at ${(plan.charge_w/1000).toFixed(2)} kW maximum, target ${plan.target_soc}%, within ${plan.window_start}-${plan.window_end}. Cheapest intervals are selected using ${plan.planning_soc}% planning SoC; ${plan.locked ? 'selection locked using actual window-start SoC' : 'selection will be recalculated using fresh SoC at window start'}. ${plan.target_energy_feasible ? '' : 'Window may be too short to reach target.'} Solar and household self-consumption stay under the existing inverter behavior.`;
  document.getElementById('plan-disclaimer').textContent=plan.note+' Observed spot values are sample-based estimates, exclude battery wear, fees and taxes, and are not supplier settlement. Missing samples are not filled. Trial expires after its delivery date; the normal night schedule then resumes.';
  document.getElementById('plan-columns').replaceChildren();
  const head = document.createElement('tr');
  for (const label of ['Start (local)','Spot EUR/kWh','Planned action','Charge limit','Target']) {const th=document.createElement('th');th.textContent=label;head.append(th);}
  document.getElementById('plan-columns').append(head);
  document.getElementById('plan-slots').replaceChildren();
  for (const slot of plan.slots) {
    const tr=document.createElement('tr');
    for (const value of [slot.local.slice(11,16)+' '+slot.local.slice(-6),slot.spot_eur_kwh.toFixed(5),slot.selected ? 'Grid charging allowed' : 'Native solar / self-consumption',slot.selected ? `${(plan.charge_w/1000).toFixed(2)} kW` : '--',slot.selected ? `${plan.target_soc}%` : '--']) {const td=document.createElement('td');td.textContent=value;tr.append(td);}
    document.getElementById('plan-slots').append(tr);
  }
}
