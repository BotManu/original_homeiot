const el = id => document.getElementById(id);
const power = value => value == null ? '—' : `${(value / 1000).toFixed(2)} kW`;
function draw(history) {
  const chart = el('chart');
  chart.replaceChildren();
  if (!history.length) return;
  const max = Math.max(1000, ...history.flatMap(s => [s.values.solar_w, s.values.load_w]));
  for (let n = 0; n < 4; n++) {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    line.setAttribute('d', `M 0 ${10 + n * 55} H 720`);
    line.setAttribute('stroke', '#edf1eb'); chart.append(line);
  }
  for (const [key, color] of [['solar_w', '#d4aa4f'], ['load_w', '#477c69']]) {
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    const span = Math.max(1, history.at(-1).ts - history[0].ts);
    line.setAttribute('points', history.map(s => `${(s.ts-history[0].ts)/span*720},${180 - s.values[key]/max*165}`).join(' '));
    line.setAttribute('fill', 'none'); line.setAttribute('stroke', color); line.setAttribute('stroke-width', '3');
    chart.append(line);
  }
  el('start').textContent = new Date(history[0].ts).toLocaleTimeString();
  el('scale').textContent = `Scale 0–${power(max)}`;
}
async function refresh() {
  try {
    const response = await fetch('/api/overview', {signal: AbortSignal.timeout(8000)});
    if (!response.ok) throw new Error('Gateway unavailable');
    const data = await response.json();
    const demo = data.mode === 'demo';
    const simulatedEdge = !demo && data.data_origin === 'simulated';
    el('mode').textContent = demo ? 'Simulator' : simulatedEdge ? 'OpenEMS · demo system' : 'OpenEMS · connected';
    el('notice').classList.toggle('error', data.stale || data.source === 'unavailable');
    el('notice').textContent = data.stale || data.source === 'unavailable'
      ? 'Energy connection unavailable. Displayed values are the last recorded measurements; physical state is unconfirmed.'
      : demo ? 'Simulator mode · These are example measurements. No equipment is connected and no commands are sent.'
      : simulatedEdge ? 'Connected to the local OpenEMS demo system · Measurements come from OpenEMS, but do not represent verified physical equipment. Energy writes are disabled.'
      : data.data_origin !== 'equipment' ? 'Reading OpenEMS locally · Equipment origin and sensor freshness have not been verified. Energy writes are disabled.'
      : data.control_enabled ? 'Local inverter control is armed. Charging follows the selected strategy and night schedule below.' : 'Reading OpenEMS locally. Energy writes are disabled until equipment qualification is complete.';
    const v = data.latest?.values;
    el('solar').textContent = power(v?.solar_w); el('load').textContent = power(v?.load_w);
    el('grid').textContent = power(v?.grid_w); el('soc').textContent = v ? `${v.battery_soc}%` : '—';
    el('grid-direction').textContent = !v ? 'Waiting for grid' : v.grid_w > 0 ? 'Importing from grid' : v.grid_w < 0 ? 'Exporting to grid' : 'Balanced';
    el('battery').textContent = !v ? 'Waiting for battery' : `${v.battery_w < 0 ? 'Charging' : v.battery_w > 0 ? 'Discharging' : 'Idle'} · ${power(Math.abs(v.battery_w))}`;
    el('updated').textContent = data.latest ? `${data.stale ? 'Last recorded' : 'Recorded'} ${new Date(data.latest.ts).toLocaleTimeString()}` : 'No measurements yet';
    el('source-name').textContent = demo ? 'Energy simulator' : 'OpenEMS Edge';
    el('source').textContent = data.source;
    el('source-detail').textContent = demo ? 'Example energy flows for interface development.' : simulatedEdge ? 'Read-only connection to the existing OpenEMS demo installation.' : data.control_enabled ? 'Local measurements and qualified inverter control.' : 'Read-only connection to local energy channels.';
    el('delivery').textContent = data.delivery;
    el('queue').textContent = `${data.buffer.pending} samples awaiting delivery · ${data.buffer.dropped} unsent samples dropped at capacity.`;
    el('retention').textContent = `Up to ${data.buffer.capacity.toLocaleString()} samples retained. Oldest samples are removed at capacity.`;
    draw(data.history);
  } catch {
    el('notice').classList.add('error');
    el('notice').textContent = 'Cannot reach the local gateway. Displayed measurements may be outdated. Reconnecting…';
    el('mode').textContent = 'Disconnected';
  } finally { setTimeout(refresh, 5000); }
}
refresh();
async function refreshGrowatt() {
  try {
    const response = await fetch('/api/devices/growatt', {signal: AbortSignal.timeout(8000)});
    if (!response.ok) throw new Error('Profile unavailable');
    const data = await response.json();
    const profile = data.profile;
    const selected = profile.connection.adapter_model;
    el('growatt-state').textContent = profile.status.replaceAll('_', ' ');
    el('growatt-model').textContent = `${profile.manufacturer} ${profile.model}`;
    const adapter = data.adapter_options[selected];
    const ports = (data.serial_ports || []).join(', ') || 'None detected';
    el('growatt-adapter').textContent = `Selected: ${selected} · ${adapter.inverter_interface} to ${adapter.network_interface}. Adapter choices: ${Object.keys(data.adapter_options).join(', ')}. Pi serial ports: ${ports}.`;
    el('growatt-notice').textContent = data.notice;
  } catch {
    el('growatt-state').textContent = 'Profile unavailable';
    el('growatt-notice').textContent = 'Unable to load the Growatt commissioning profile. Equipment connection is unconfirmed.';
  } finally { setTimeout(refreshGrowatt, 15000); }
}
refreshGrowatt();

let controlReady = false;
let nightEnabled = false;
function updateControlButton() { el('strategy-submit').disabled = el('strategy').value !== 'MONITOR' && !controlReady; }
async function refreshControl() {
  try {
    const response = await fetch('/api/energy/control', {signal: AbortSignal.timeout(8000)});
    if (!response.ok) throw new Error();
    const data = await response.json();
    el('charge-w').max=data.max_charge_w;
    controlReady = data.control_ready === true;
    if(data.night_schedule) { nightEnabled=data.night_schedule.enabled; el('night-schedule-toggle').textContent=nightEnabled ? 'Pause automatic night charging' : 'Enable automatic night charging'; }
    if(data.night_schedule) el('night-schedule-status').textContent = `Night grid charging: ${data.night_schedule.start}?${data.night_schedule.end} ${data.night_schedule.timezone}; target ${data.night_schedule.target_soc}%, ${(data.night_schedule.charge_w/1000).toFixed(2)} kW. ${data.night_schedule.enabled ? 'Scheduled; native qualification required.' : 'Disabled.'}`;
    el('control-status').textContent = `${data.status}: ${data.reason}. Operating cap ${(data.max_charge_w/1000).toFixed(2)} kW. Hardware writes ${controlReady ? 'enabled' : 'blocked'}. Physical effect verified: ${data.physical_effect_verified === true ? 'yes' : 'no'}.`;
    if(data.run_active && data.run_until_ms) el('control-status').textContent += ` Charging time remaining: ${Math.max(0,Math.ceil((data.run_until_ms-Date.now())/1000))} seconds.`;
    el('control-blockers').replaceChildren();
    for (const [key, value] of Object.entries(data.qualification || {})) {
      if (value !== true && !(key === 'inverter_discharge_reserve_verified' && data.min_discharge_soc === 0)) { const li = document.createElement('li'); li.textContent = key.replaceAll('_', ' '); el('control-blockers').append(li); }
    }
  } catch { controlReady = false; el('control-status').textContent = 'Controller unavailable. Hardware state unconfirmed.'; }
  updateControlButton(); setTimeout(refreshControl, 5000);
}
el('strategy').addEventListener('change', updateControlButton);
el('strategy-form').addEventListener('submit', async event => {
  event.preventDefault(); el('strategy-submit').disabled = true;
  try {
    const mode = el('strategy').value;
    const response = await fetch('/api/energy/control', {method:'POST', headers:{'Content-Type':'application/json','X-Gateway-Control':'1'}, body:JSON.stringify({mode,charge_w:mode === 'MONITOR' ? 0 : Number(el('charge-w').value),duration_s:Number(el('duration').value),target_soc:Number(el('target-soc').value)}), signal:AbortSignal.timeout(8000)});
    const result = await response.json();
    el('command-result').textContent = response.ok ? `Request ${result.command_id} submitted; application unconfirmed.` : result.error;
  } catch { el('command-result').textContent = 'Response unavailable. Check controller status before retrying.'; }
  updateControlButton();
});
refreshControl();

el('night-schedule-toggle').addEventListener('click',async () => {
  el('night-schedule-toggle').disabled=true;
  try {
    const response=await fetch('/api/energy/night-schedule',{method:'POST',headers:{'Content-Type':'application/json','X-Gateway-Control':'1'},body:JSON.stringify({enabled:!nightEnabled}),signal:AbortSignal.timeout(8000)});
    const data=await response.json();
    el('command-result').textContent=response.ok ? `Night schedule ${data.night_schedule.enabled ? 'enabled' : 'paused'}: ${data.state.replaceAll('_',' ')}. Hardware application remains subject to OpenEMS qualification.` : data.error;
    if(response.ok) {nightEnabled=data.night_schedule.enabled;el('night-schedule-toggle').textContent=nightEnabled ? 'Pause automatic night charging' : 'Enable automatic night charging';}
  } catch {el('command-result').textContent='Unable to update night schedule.';}
  el('night-schedule-toggle').disabled=false;
});


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

loadDayPlan('/api/energy/plan');

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
