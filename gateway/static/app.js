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
      : 'Reading OpenEMS locally. Energy writes are disabled until equipment qualification is complete.';
    const v = data.latest?.values;
    el('solar').textContent = power(v?.solar_w); el('load').textContent = power(v?.load_w);
    el('grid').textContent = power(v?.grid_w); el('soc').textContent = v ? `${v.battery_soc}%` : '—';
    el('grid-direction').textContent = !v ? 'Waiting for grid' : v.grid_w > 0 ? 'Importing from grid' : v.grid_w < 0 ? 'Exporting to grid' : 'Balanced';
    el('battery').textContent = !v ? 'Waiting for battery' : `${v.battery_w < 0 ? 'Charging' : v.battery_w > 0 ? 'Discharging' : 'Idle'} · ${power(Math.abs(v.battery_w))}`;
    el('updated').textContent = data.latest ? `${data.stale ? 'Last recorded' : 'Recorded'} ${new Date(data.latest.ts).toLocaleTimeString()}` : 'No measurements yet';
    el('source-name').textContent = demo ? 'Energy simulator' : 'OpenEMS Edge';
    el('source').textContent = data.source;
    el('source-detail').textContent = demo ? 'Example energy flows for interface development.' : simulatedEdge ? 'Read-only connection to the existing OpenEMS demo installation.' : 'Read-only connection to local energy channels.';
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
    el('growatt-adapter').textContent = `Selected: ${selected} · ${data.adapter_options[selected].inverter_interface} to Wi-Fi. Adapter choices: ${Object.keys(data.adapter_options).join(', ')}.`;
    el('growatt-notice').textContent = data.notice;
  } catch {
    el('growatt-state').textContent = 'Profile unavailable';
    el('growatt-notice').textContent = 'Unable to load the Growatt commissioning profile. Equipment connection is unconfirmed.';
  } finally { setTimeout(refreshGrowatt, 15000); }
}
refreshGrowatt();
