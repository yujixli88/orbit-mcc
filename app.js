const $ = id => document.getElementById(id);
const cv = $('map'), ctx = cv.getContext('2d');
let S = null, trail = [], track = [], t0 = 0;

// Необязательно: положи карту мира (equirectangular 2:1) в assets/world.jpg
const world = new Image(); let worldOk = false;
world.onload = () => worldOk = true; world.src = 'assets/world.jpg';

const xy = (lat, lon) => [(lon + 180) / 360 * cv.width, (90 - lat) / 180 * cv.height];

function line(pts, color, dash = []) {
  ctx.strokeStyle = color; ctx.setLineDash(dash); ctx.lineWidth = 2; ctx.beginPath();
  let prev = null;
  for (const [la, lo] of pts) {
    const [x, y] = xy(la, lo);
    (prev === null || Math.abs(lo - prev) > 180) ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    prev = lo;
  }
  ctx.stroke(); ctx.setLineDash([]);
}

function draw(ts) {
  ctx.clearRect(0, 0, cv.width, cv.height);
  if (worldOk) { ctx.globalAlpha = .55; ctx.drawImage(world, 0, 0, cv.width, cv.height); ctx.globalAlpha = 1; }
  ctx.strokeStyle = '#16213a'; ctx.lineWidth = 1;
  for (let lo = -180; lo <= 180; lo += 30) { const [x] = xy(0, lo); ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, cv.height); ctx.stroke(); }
  for (let la = -90; la <= 90; la += 30) { const [, y] = xy(la, 0); ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(cv.width, y); ctx.stroke(); }
  if (S) {
    line(track, '#4a5b8a', [6, 6]); line(trail, '#6c8cff');
    const [gx, gy] = xy(...S.gs);
    ctx.fillStyle = '#ffc233'; ctx.fillRect(gx - 5, gy - 5, 10, 10);
    const [sx, sy] = xy(S.lat, S.lon);
    if (S.signal > 0) { ctx.strokeStyle = 'rgba(46,229,157,.6)'; ctx.setLineDash([3, 4]); ctx.beginPath(); ctx.moveTo(gx, gy); ctx.lineTo(sx, sy); ctx.stroke(); ctx.setLineDash([]); }
    const pulse = 8 + 4 * Math.sin(ts / 300);
    ctx.fillStyle = 'rgba(108,140,255,.25)'; ctx.beginPath(); ctx.arc(sx, sy, pulse + 6, 0, 7); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(sx, sy, 6, 0, 7); ctx.fill();
  }
  requestAnimationFrame(draw);
}

function tile(label, val, unit, pct, cls = '') {
  return `<div class="tile ${cls}"><span>${label}</span><b>${val}<small> ${unit}</small></b>` +
    (pct != null ? `<div class="bar"><i style="width:${pct}%;background:var(--${cls || 'ok'})"></i></div>` : '') + `</div>`;
}

function render(d) {
  S = d; trail.push([d.lat, d.lon]); if (trail.length > 400) trail.shift();
  $('sunState').textContent = d.sun ? '☀ на свету' : '🌑 в тени Земли';
  $('telemetry').innerHTML =
    tile('Заряд батареи', d.battery, '%', d.battery, d.battery < 5 ? 'err' : d.battery < 20 ? 'warn' : '') +
    tile('Температура', d.temp, '°C', null, (d.temp > 60 || d.temp < -30) ? 'warn' : '') +
    tile('Скорость', d.speed, 'км/с') +
    tile('Высота орбиты', d.alt, 'км') +
    tile('Уровень сигнала', d.signal, '%', d.signal, d.signal === 0 ? 'err' : d.signal < 40 ? 'warn' : '') +
    tile('Топливо', d.fuel, '%', d.fuel, d.fuel < 10 ? 'warn' : '') +
    tile('Период', d.period, 'мин') +
    tile('Снимков', d.photos, 'шт') +
    tile('Широта / долгота', d.lat.toFixed(1) + '° / ' + d.lon.toFixed(1) + '°', '');
  $('modules').innerHTML = Object.entries(d.modules).map(([k, m]) =>
    `<li class="${m.status}"><i class="led"></i><span class="name" style="color:var(--text)">${m.name}</span><span class="note">${m.note}</span></li>`).join('');
  if (!$('rebootSel').children.length)
    $('rebootSel').innerHTML = Object.entries(d.modules).map(([k, m]) => `<option value="${k}">${m.name}</option>`).join('');
  $('log').innerHTML = d.log.slice().reverse().map(l => `<li class="${l.level}">[${l.time}] ${l.msg}</li>`).join('');
}

async function loadTrack() { track = await (await fetch('/api/track')).json(); }

function connect() {
  const ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws');
  ws.onopen = () => { $('conn').textContent = 'онлайн'; $('conn').className = 'pill ok'; loadTrack(); };
  ws.onmessage = e => { render(JSON.parse(e.data)); if (++t0 % 20 === 0) loadTrack(); };
  ws.onclose = () => { $('conn').textContent = 'нет соединения'; $('conn').className = 'pill err'; setTimeout(connect, 2000); };
}

document.querySelectorAll('button[data-cmd]').forEach(b => b.onclick = async () => {
  let arg = b.dataset.arg === 'select' ? $('rebootSel').value : b.dataset.arg;
  await fetch('/api/command', { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ cmd: b.dataset.cmd, arg }) });
});

connect(); requestAnimationFrame(draw);
