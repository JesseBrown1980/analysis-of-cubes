const TAU = Math.PI * 2;
const SQRT2 = Math.sqrt(2);
const LAYERS = ['topology', 'shell12', 'evidence', 'causal'];

const EDGE_SECTORS = [
  [1, 1, 0], [1, -1, 0], [-1, 1, 0], [-1, -1, 0],
  [1, 0, 1], [1, 0, -1], [-1, 0, 1], [-1, 0, -1],
  [0, 1, 1], [0, 1, -1], [0, -1, 1], [0, -1, -1]
].map((vector, index) => ({
  id: `S${String(index + 1).padStart(2, '0')}`,
  phase: index * 30,
  vector: vector.map((value) => value / SQRT2)
}));

const layerCopy = {
  topology: {
    code: 'LAYER 01',
    title: 'NÚCLEO CANÔNICO 06',
    copy: 'A junção interna permanece Ω + seis vetores direcionais: ±X, ±Y e ±Z.',
    labels: ['NÓS', 'VETORES', 'EIXOS']
  },
  shell12: {
    code: 'LAYER 02',
    title: 'CASCA PROJETIVA 12',
    copy: 'Doze interfaces nos meios de aresta do cubo; oito expostas e quatro ocluídas pela projeção.',
    labels: ['SETORES', 'VISÍVEIS', 'OCLUÍDOS']
  },
  evidence: {
    code: 'LAYER 03',
    title: 'RADAR DE EVIDÊNCIAS',
    copy: 'Hash-pinned, declarado e retido permanecem estados distintos. A casca não promove hipótese a Canon.',
    labels: ['VERIFICADOS', 'DECLARADOS', 'FALHAS']
  },
  causal: {
    code: 'LAYER 04',
    title: 'FLUXO CAUSAL',
    copy: 'Ω semeia, os seis setores produzem recibos, o gate sela e um novo root pode emergir.',
    labels: ['SELOS', 'ÉPOCA', 'ROLLBACK']
  }
};

const link = document.createElement('link');
link.rel = 'stylesheet';
link.href = '/immersion-shell.css';
document.head.append(link);

const canvas = document.createElement('canvas');
canvas.id = 'projection-canvas';
canvas.setAttribute('aria-hidden', 'true');
document.body.append(canvas);

const depth = document.createElement('div');
depth.className = 'immersion-depth-field';
depth.setAttribute('aria-hidden', 'true');
depth.innerHTML = '<i></i><i></i><i></i><i></i>';
document.body.append(depth);

const ui = document.createElement('section');
ui.className = 'immersion-shell-ui';
ui.innerHTML = `
  <nav class="immersion-switcher" aria-label="Camadas de imersão">
    <button data-immersion="topology" aria-pressed="false"><b>01</b>NÚCLEO 06</button>
    <button data-immersion="shell12" aria-pressed="true"><b>02</b>CASCA 12</button>
    <button data-immersion="evidence" aria-pressed="false"><b>03</b>EVIDÊNCIA</button>
    <button data-immersion="causal" aria-pressed="false"><b>04</b>CAUSAL</button>
  </nav>
  <div class="immersion-badge" id="immersion-badge">HIPÓTESE C8 · 12 SETORES · TESTE 30°</div>
  <aside class="immersion-console" aria-live="polite">
    <header><span>CAMADA DE IMERSÃO</span><b id="immersion-code">LAYER 02</b></header>
    <h3 id="immersion-title">CASCA PROJETIVA 12</h3>
    <p id="immersion-copy"></p>
    <div class="immersion-metrics">
      <div><small id="immersion-label-a">SETORES</small><strong id="immersion-value-a">12</strong></div>
      <div><small id="immersion-label-b">VISÍVEIS</small><strong id="immersion-value-b">08</strong></div>
      <div><small id="immersion-label-c">OCLUÍDOS</small><strong id="immersion-value-c">04</strong></div>
    </div>
    <div class="immersion-signal" id="immersion-signal" aria-hidden="true"></div>
    <footer><span><kbd>M</kbd> ALTERNAR</span><b id="immersion-integrity">MODELO · FALSIFICÁVEL</b></footer>
  </aside>`;
document.body.append(ui);

const elements = {
  code: ui.querySelector('#immersion-code'),
  title: ui.querySelector('#immersion-title'),
  copy: ui.querySelector('#immersion-copy'),
  labelA: ui.querySelector('#immersion-label-a'),
  labelB: ui.querySelector('#immersion-label-b'),
  labelC: ui.querySelector('#immersion-label-c'),
  valueA: ui.querySelector('#immersion-value-a'),
  valueB: ui.querySelector('#immersion-value-b'),
  valueC: ui.querySelector('#immersion-value-c'),
  signal: ui.querySelector('#immersion-signal'),
  integrity: ui.querySelector('#immersion-integrity'),
  badge: ui.querySelector('#immersion-badge')
};

elements.signal.replaceChildren(...Array.from({ length: 24 }, (_, index) => {
  const bar = document.createElement('i');
  bar.style.setProperty('--signal-height', `${5 + ((index * 11) % 17)}px`);
  bar.style.setProperty('--signal-opacity', String(.25 + (index % 5) * .13));
  return bar;
}));

const ctx = canvas.getContext('2d', { alpha: true, desynchronized: true });
let width = 0;
let height = 0;
let dpr = 1;
let state = null;
let layer = readLayer();
let yaw = -.54;
let pitch = -.28;
let targetYaw = yaw;
let targetPitch = pitch;
let pointer = null;
let elapsed = 0;
let last = performance.now();

function readLayer() {
  try {
    const stored = localStorage.getItem('relic.immersion.layer');
    return LAYERS.includes(stored) ? stored : 'shell12';
  } catch {
    return 'shell12';
  }
}

function setLayer(next, announce = true) {
  if (!LAYERS.includes(next)) return;
  layer = next;
  document.body.dataset.immersionLayer = layer;
  ui.querySelectorAll('[data-immersion]').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.immersion === layer));
  });
  try { localStorage.setItem('relic.immersion.layer', layer); } catch {}
  renderPanel();
  if (announce) {
    const toast = document.querySelector('#toast');
    if (toast) {
      toast.textContent = `${layerCopy[layer].title} · CAMADA ATIVA`;
      toast.classList.add('visible');
      setTimeout(() => toast.classList.remove('visible'), 1800);
    }
  }
}

function cycleLayer() {
  const index = LAYERS.indexOf(layer);
  setLayer(LAYERS[(index + 1) % LAYERS.length]);
}

function renderPanel() {
  const copy = layerCopy[layer];
  elements.code.textContent = copy.code;
  elements.title.textContent = copy.title;
  elements.copy.textContent = copy.copy;
  [elements.labelA.textContent, elements.labelB.textContent, elements.labelC.textContent] = copy.labels;

  const canon = state?.body?.canon || {};
  const previous = state?.body?.previousRoot;
  const metrics = {
    topology: ['07', '06', '03'],
    shell12: ['12', '08', '04'],
    evidence: [
      String(canon.verified ?? 0).padStart(2, '0'),
      String(canon.declared ?? 0).padStart(2, '0'),
      String(canon.failures ?? 0).padStart(2, '0')
    ],
    causal: [
      `${state?.gate?.sealed ?? 0}/${state?.gate?.required ?? 6}`,
      state ? state.epoch.toString(16).toUpperCase().slice(0, 6) : '------',
      previous ? 'ARMADO' : 'VAZIO'
    ]
  }[layer];

  [elements.valueA.textContent, elements.valueB.textContent, elements.valueC.textContent] = metrics;
  elements.integrity.textContent = {
    topology: 'CANON INTERNO · 6 VETORES',
    shell12: 'HIPÓTESE C8 · TESTE 30°',
    evidence: canon.status === 'SEALED' ? 'CANON · SEALED' : 'CANON · HELD',
    causal: state?.gate?.status === 'COMMITTED' ? 'GATE · COMMITTED' : 'GATE · HELD'
  }[layer];
  elements.badge.textContent = {
    topology: 'J = { Ω, ±X, ±Y, ±Z }',
    shell12: 'HIPÓTESE C8 · 8/12 VISÍVEIS · TESTE 30°',
    evidence: `${canon.verified ?? 0}/${canon.artifacts ?? 0} HASH-PINNED · ${canon.declared ?? 0} DECLARADOS`,
    causal: state ? `Ω EPOCH ${state.epoch.toString(16).toUpperCase().padStart(8, '0')}` : 'Ω EPOCH —'
  }[layer];

  [...elements.signal.children].forEach((bar, index) => {
    const wave = .5 + .5 * Math.sin(elapsed * 1.8 + index * .72);
    const base = layer === 'causal' ? 19 : layer === 'evidence' ? 15 : 11;
    bar.style.setProperty('--signal-height', `${4 + wave * base}px`);
    bar.style.setProperty('--signal-opacity', String(.22 + wave * .68));
  });
}

function resize() {
  dpr = Math.min(1.25, window.devicePixelRatio || 1);
  width = innerWidth;
  height = innerHeight;
  canvas.width = Math.max(1, Math.floor(width * dpr));
  canvas.height = Math.max(1, Math.floor(height * dpr));
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function rotate([x, y, z]) {
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  const x1 = x * cy - z * sy;
  const z1 = x * sy + z * cy;
  return [x1, y * cp - z1 * sp, y * sp + z1 * cp];
}

function stage() {
  const left = width > 760 ? (width > 1050 ? 235 : 195) : 68;
  const right = width > 1050 ? 294 : (width > 760 ? 260 : 0);
  const centerX = left + (width - left - right) * .5;
  const centerY = 94 + (height - 170) * .48;
  const base = Math.min(width - left - right, height - 190) * .39;
  return { centerX, centerY, base };
}

function project(vector, radius = 1) {
  const { centerX, centerY, base } = stage();
  const [x, y, z] = rotate(vector.map((value) => value * radius));
  const perspective = 1 / (1.7 - z * .17);
  return { x: centerX + x * base * perspective, y: centerY + y * base * perspective, z, scale: perspective };
}

function shellPoints() {
  const ranked = EDGE_SECTORS
    .map((sector) => ({ ...project(sector.vector, 1.22), sector }))
    .sort((a, b) => b.z - a.z);
  const visible = new Set(ranked.slice(0, 8).map((point) => point.sector.id));
  return EDGE_SECTORS.map((sector) => ({ ...project(sector.vector, 1.22), sector, visible: visible.has(sector.id) }));
}

function connected(left, right) {
  const distance = Math.hypot(
    left.sector.vector[0] - right.sector.vector[0],
    left.sector.vector[1] - right.sector.vector[1],
    left.sector.vector[2] - right.sector.vector[2]
  );
  return distance < 1.02;
}

function drawSectorRing(centerX, centerY, radius, visibleCount = 8) {
  for (let index = 0; index < 12; index += 1) {
    const start = -Math.PI / 2 + index * TAU / 12 + .025;
    const end = start + TAU / 12 - .05;
    const exposed = index < visibleCount;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, start, end);
    ctx.strokeStyle = exposed
      ? `rgba(212,255,99,${layer === 'shell12' ? .68 : .22})`
      : 'rgba(118,149,143,.13)';
    ctx.lineWidth = exposed ? 2 : 1;
    ctx.setLineDash(exposed ? [] : [2, 5]);
    ctx.stroke();
  }
  ctx.setLineDash([]);
}

function drawShell(points) {
  const { centerX, centerY, base } = stage();
  const shellAlpha = layer === 'shell12' ? 1 : layer === 'topology' ? .12 : .62;

  for (let a = 0; a < points.length; a += 1) {
    for (let b = a + 1; b < points.length; b += 1) {
      if (!connected(points[a], points[b])) continue;
      const exposed = points[a].visible && points[b].visible;
      ctx.beginPath();
      ctx.moveTo(points[a].x, points[a].y);
      ctx.lineTo(points[b].x, points[b].y);
      ctx.strokeStyle = exposed
        ? `rgba(212,255,99,${.14 * shellAlpha})`
        : `rgba(118,149,143,${.07 * shellAlpha})`;
      ctx.lineWidth = exposed ? .9 : .55;
      ctx.setLineDash(exposed ? [] : [2, 6]);
      ctx.stroke();
    }
  }
  ctx.setLineDash([]);

  for (const point of [...points].sort((a, b) => a.z - b.z)) {
    const exposed = point.visible;
    const size = (exposed ? 7 : 5) * (.85 + point.scale * .3);
    ctx.save();
    ctx.translate(point.x, point.y);
    ctx.rotate(elapsed * .11 + point.sector.phase * Math.PI / 180);
    ctx.beginPath();
    ctx.moveTo(0, -size);
    ctx.lineTo(size, 0);
    ctx.lineTo(0, size);
    ctx.lineTo(-size, 0);
    ctx.closePath();
    ctx.fillStyle = exposed
      ? `rgba(212,255,99,${.12 * shellAlpha})`
      : `rgba(118,149,143,${.035 * shellAlpha})`;
    ctx.strokeStyle = exposed
      ? `rgba(212,255,99,${.72 * shellAlpha})`
      : `rgba(118,149,143,${.22 * shellAlpha})`;
    ctx.lineWidth = exposed ? 1.2 : .7;
    ctx.setLineDash(exposed ? [] : [2, 3]);
    ctx.fill();
    ctx.stroke();
    ctx.restore();

    if (layer === 'shell12' || layer === 'evidence') {
      ctx.textAlign = 'center';
      ctx.font = '7px Cascadia Mono, monospace';
      ctx.fillStyle = exposed ? 'rgba(212,255,99,.7)' : 'rgba(118,149,143,.3)';
      ctx.fillText(`${point.sector.id} · ${point.sector.phase}°`, point.x, point.y + size + 11);
    }
  }

  drawSectorRing(centerX, centerY, base * .59, 8);
}

function drawEvidence() {
  if (layer !== 'evidence') return;
  const { centerX, centerY, base } = stage();
  const canon = state?.body?.canon || {};
  const total = Math.max(1, canon.artifacts || 1);
  const ratio = (canon.verified || 0) / total;
  ctx.save();
  ctx.translate(centerX, centerY);
  ctx.rotate(-Math.PI / 2);
  ctx.beginPath();
  ctx.arc(0, 0, base * .24, 0, TAU);
  ctx.strokeStyle = 'rgba(255,200,87,.09)';
  ctx.lineWidth = 5;
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(0, 0, base * .24, 0, TAU * ratio);
  ctx.strokeStyle = 'rgba(255,200,87,.72)';
  ctx.shadowColor = '#ffc857';
  ctx.shadowBlur = 12;
  ctx.stroke();
  ctx.restore();
  ctx.shadowBlur = 0;
}

function drawCausal(points) {
  if (layer !== 'causal') return;
  const { centerX, centerY } = stage();
  for (let index = 0; index < points.length; index += 1) {
    const point = points[index];
    const inward = index % 2 === 0;
    for (let pulse = 0; pulse < 2; pulse += 1) {
      let t = (elapsed * .18 + index / 12 + pulse * .5) % 1;
      if (!inward) t = 1 - t;
      const x = point.x + (centerX - point.x) * t;
      const y = point.y + (centerY - point.y) * t;
      const alpha = Math.sin(t * Math.PI) * .72;
      ctx.fillStyle = `rgba(138,125,255,${alpha})`;
      ctx.fillRect(x - 1.2, y - 1.2, 2.4, 2.4);
    }
  }
}

function draw() {
  ctx.clearRect(0, 0, width, height);
  if (layer === 'topology') return;
  const points = shellPoints();
  drawShell(points);
  drawEvidence();
  drawCausal(points);
}

function tick(now) {
  const delta = Math.min(.05, (now - last) / 1000);
  last = now;
  elapsed += delta;
  yaw += (targetYaw - yaw) * .08;
  pitch += (targetPitch - pitch) * .08;
  if (!pointer) targetYaw += delta * (layer === 'shell12' ? .045 : .018);
  draw();
  if (Math.floor(elapsed * 3) !== Math.floor((elapsed - delta) * 3)) renderPanel();
  requestAnimationFrame(tick);
}

const omegaCanvas = document.querySelector('#omega-canvas');
omegaCanvas?.addEventListener('pointerdown', (event) => {
  pointer = { id: event.pointerId, x: event.clientX, y: event.clientY, yaw: targetYaw, pitch: targetPitch };
});
omegaCanvas?.addEventListener('pointermove', (event) => {
  if (!pointer || pointer.id !== event.pointerId) return;
  targetYaw = pointer.yaw + (event.clientX - pointer.x) * .005;
  targetPitch = Math.max(-1.1, Math.min(1.1, pointer.pitch + (event.clientY - pointer.y) * .004));
});
omegaCanvas?.addEventListener('pointerup', (event) => {
  if (pointer?.id === event.pointerId) pointer = null;
});
omegaCanvas?.addEventListener('pointercancel', () => { pointer = null; });

ui.querySelectorAll('[data-immersion]').forEach((button) => {
  button.addEventListener('click', () => setLayer(button.dataset.immersion));
});

window.addEventListener('keydown', (event) => {
  if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;
  if (event.key.toLowerCase() === 'm') cycleLayer();
  else if (/^[1-4]$/.test(event.key)) setLayer(LAYERS[Number(event.key) - 1]);
});
window.addEventListener('resize', resize, { passive: true });

const interfaceRoot = document.querySelector('#interface');
if (interfaceRoot) {
  new MutationObserver(() => {
    ui.classList.toggle('hud-hidden', interfaceRoot.classList.contains('hud-hidden'));
  }).observe(interfaceRoot, { attributes: true, attributeFilter: ['class'] });
}

fetch('/api/state', { cache: 'no-store' })
  .then((response) => response.ok ? response.json() : Promise.reject(new Error('STATE_UNAVAILABLE')))
  .then((nextState) => { state = nextState; renderPanel(); })
  .catch(() => { elements.integrity.textContent = 'ESTADO · INDISPONÍVEL'; });

resize();
setLayer(layer, false);
requestAnimationFrame((now) => { last = now; tick(now); });
