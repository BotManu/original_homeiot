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
  if (siteId) await refresh();
  else { el('notice').textContent = 'No sites are assigned to this account.'; el('export').disabled = true; }
}
el('site-select').addEventListener('change', () => {siteId = el('site-select').value; refresh();});
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
