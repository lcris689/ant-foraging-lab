const COLORS = {
  A: '#b8553d',
  B: '#c58b22',
  C: '#3c6f98',
  uncommitted: '#6f6d66',
  nest: '#315f45',
  carrying: '#f2d36e',
};

const PRESETS = {
  guided: {
    description: 'A compact teaching setup that makes discovery, recruitment, and delivery easier to observe. It is not comparative evidence.',
    seed: 689,
    antCount: 120,
    gridSize: 40,
    maxSteps: 400,
    frameStride: 4,
    terminationPolicy: 'fixed_steps',
    nest: { x: 20, y: 20 },
    feeders: {
      A: { x: 10, y: 20, quality: 1, food: 1000, recruitment: .75, attrition: .003 },
      B: { x: 30, y: 20, quality: 1, food: 1000, recruitment: .75, attrition: .003 },
      C: { x: 20, y: 30, quality: 1, food: 1000, recruitment: .75, attrition: .003 },
    },
  },
  reference: {
    description: 'The published 100 × 100 reference configuration. Exact-cell discovery is intentionally sparse and is best interpreted across seed sets.',
    seed: 689,
    antCount: 200,
    gridSize: 100,
    maxSteps: 1000,
    frameStride: 10,
    terminationPolicy: 'fixed_steps',
    nest: { x: 50, y: 50 },
    feeders: {
      A: { x: 25, y: 75, quality: .75, food: 1000, recruitment: .75, attrition: .009 },
      B: { x: 75, y: 25, quality: .75, food: 1000, recruitment: .75, attrition: .009 },
      C: { x: 75, y: 75, quality: .75, food: 1000, recruitment: .75, attrition: .009 },
    },
  },
  noRecruitment: {
    description: 'The guided setup with recruitment set to zero. Compare it with the guided demo using the same seed.',
    seed: 689,
    antCount: 120,
    gridSize: 40,
    maxSteps: 400,
    frameStride: 4,
    terminationPolicy: 'fixed_steps',
    nest: { x: 20, y: 20 },
    feeders: {
      A: { x: 10, y: 20, quality: 1, food: 1000, recruitment: 0, attrition: .003 },
      B: { x: 30, y: 20, quality: 1, food: 1000, recruitment: 0, attrition: .003 },
      C: { x: 20, y: 30, quality: 1, food: 1000, recruitment: 0, attrition: .003 },
    },
  },
};

const form = document.querySelector('#experiment-form');
const runButton = document.querySelector('#run-button');
const formMessage = document.querySelector('#form-message');
const presetSelect = document.querySelector('#preset');
const presetNote = document.querySelector('#preset-note');
const apiIndicator = document.querySelector('#api-indicator');
const apiStatus = document.querySelector('#api-status');
const canvas = document.querySelector('#simulation-canvas');
const context = canvas.getContext('2d');
const canvasEmpty = document.querySelector('#canvas-empty');
const timeline = document.querySelector('#timeline');
const playButton = document.querySelector('#play-button');
const playbackSpeed = document.querySelector('#playback-speed');
const stepValue = document.querySelector('#step-value');
const chart = document.querySelector('#food-chart');
const chartEmpty = document.querySelector('#chart-empty');
const historyBody = document.querySelector('#history-body');
const eventLog = document.querySelector('#event-log');

let currentTrace = null;
let currentFrameIndex = 0;
let playbackTimer = null;
let runHistory = loadHistory();
let renderedEventCount = -1;

function numberValue(selector) {
  return Number(document.querySelector(selector).value);
}

function setValue(selector, value) {
  document.querySelector(selector).value = String(value);
}

function applyPreset(presetName) {
  const preset = PRESETS[presetName];
  if (!preset) {
    presetNote.textContent = 'Custom settings. Change one variable at a time when comparing runs.';
    return;
  }

  setValue('#seed', preset.seed);
  setValue('#ant-count', preset.antCount);
  setValue('#grid-size', preset.gridSize);
  setValue('#max-steps', preset.maxSteps);
  setValue('#frame-stride', preset.frameStride);
  setValue('#termination-policy', preset.terminationPolicy);
  setValue('#nest-x', preset.nest.x);
  setValue('#nest-y', preset.nest.y);
  Object.entries(preset.feeders).forEach(([feederId, feeder]) => {
    const panel = document.querySelector(`[data-feeder-form="${feederId}"]`);
    Object.entries(feeder).forEach(([field, value]) => {
      panel.querySelector(`[data-field="${field}"]`).value = String(value);
    });
  });
  presetNote.textContent = preset.description;
}

function feederPayload(feederId) {
  const panel = document.querySelector(`[data-feeder-form="${feederId}"]`);
  const value = (field) => Number(panel.querySelector(`[data-field="${field}"]`).value);
  return {
    feeder_id: feederId,
    position: { x: value('x'), y: value('y') },
    quality: value('quality'),
    recruitment_rate: value('recruitment'),
    attrition_rate: value('attrition'),
    food: value('food'),
  };
}

function buildPayload() {
  return {
    seed: numberValue('#seed'),
    grid_size: numberValue('#grid-size'),
    nest: { x: numberValue('#nest-x'), y: numberValue('#nest-y') },
    ant_count: numberValue('#ant-count'),
    max_steps: numberValue('#max-steps'),
    frame_stride: numberValue('#frame-stride'),
    termination_policy: document.querySelector('#termination-policy').value,
    feeders: ['A', 'B', 'C'].map(feederPayload),
  };
}

function setMessage(message, isError = false) {
  formMessage.textContent = message;
  formMessage.classList.toggle('is-error', isError);
}

function errorMessage(errorBody) {
  if (Array.isArray(errorBody?.detail)) {
    return errorBody.detail.map((item) => item.msg).join(' ');
  }
  return errorBody?.detail || 'The experiment could not be completed.';
}

async function runExperiment(event) {
  if (event) event.preventDefault();
  stopPlayback();
  runButton.disabled = true;
  runButton.textContent = 'Running…';
  setMessage('Computing the seeded simulation.');

  try {
    const response = await fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(buildPayload()),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(errorMessage(body));

    currentTrace = body;
    currentFrameIndex = 0;
    renderedEventCount = -1;
    timeline.max = String(body.frames.length - 1);
    timeline.value = String(currentFrameIndex);
    timeline.disabled = false;
    playButton.disabled = body.frames.length < 2;
    canvasEmpty.hidden = true;
    document.querySelector('#export-json').disabled = false;
    recordRun(body);
    renderCurrentFrame();
    renderChart();
    setMessage(`Computed ${body.result.steps.toLocaleString()} steps from seed ${body.result.seed}. Replaying from the start.`);
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches && body.frames.length > 1) {
      startPlayback();
    }
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    runButton.disabled = false;
    runButton.textContent = 'Run experiment';
  }
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.max(1, Math.round(rect.width * ratio));
  const height = Math.max(1, Math.round(rect.height * ratio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  renderCurrentFrame();
}

function canvasPoint(position, gridSize, padding, width, height) {
  const drawableWidth = width - padding * 2;
  const drawableHeight = height - padding * 2;
  return {
    x: padding + (position.x / Math.max(1, gridSize - 1)) * drawableWidth,
    y: padding + (position.y / Math.max(1, gridSize - 1)) * drawableHeight,
  };
}

function drawGrid(width, height, padding) {
  context.fillStyle = '#f8f5ed';
  context.fillRect(0, 0, width, height);
  context.strokeStyle = '#d8d1c5';
  context.lineWidth = 1;
  context.beginPath();
  for (let index = 0; index <= 10; index += 1) {
    const x = padding + ((width - padding * 2) * index) / 10;
    const y = padding + ((height - padding * 2) * index) / 10;
    context.moveTo(x, padding);
    context.lineTo(x, height - padding);
    context.moveTo(padding, y);
    context.lineTo(width - padding, y);
  }
  context.stroke();
  context.strokeStyle = '#9d9588';
  context.strokeRect(padding, padding, width - padding * 2, height - padding * 2);
}

function drawSimulation(frame) {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const width = canvas.width;
  const height = canvas.height;
  const padding = 22 * ratio;
  const gridSize = currentTrace.config.grid_size;
  drawGrid(width, height, padding);

  const nest = canvasPoint(currentTrace.config.nest, gridSize, padding, width, height);
  context.fillStyle = COLORS.nest;
  context.strokeStyle = '#fffdf7';
  context.lineWidth = 2 * ratio;
  context.beginPath();
  context.rect(nest.x - 7 * ratio, nest.y - 7 * ratio, 14 * ratio, 14 * ratio);
  context.fill();
  context.stroke();

  currentTrace.config.feeders.forEach((feeder) => {
    const point = canvasPoint(feeder.position, gridSize, padding, width, height);
    context.save();
    context.translate(point.x, point.y);
    context.rotate(Math.PI / 4);
    context.fillStyle = COLORS[feeder.feeder_id] || '#805d91';
    context.fillRect(-7 * ratio, -7 * ratio, 14 * ratio, 14 * ratio);
    context.strokeStyle = '#fffdf7';
    context.strokeRect(-7 * ratio, -7 * ratio, 14 * ratio, 14 * ratio);
    context.restore();
  });

  const antRadius = Math.max(1.7, Math.min(3.2, 300 / currentTrace.config.ant_count)) * ratio;
  frame.ants.forEach((ant) => {
    const point = canvasPoint(ant.position, gridSize, padding, width, height);
    const antColor = ant.commitment ? (COLORS[ant.commitment] || '#805d91') : COLORS.uncommitted;
    context.beginPath();
    context.arc(point.x, point.y, antRadius, 0, Math.PI * 2);
    context.fillStyle = antColor;
    context.globalAlpha = .78;
    context.fill();
    context.globalAlpha = 1;
    if (ant.holding_food) {
      context.lineWidth = Math.max(1, ratio);
      context.strokeStyle = COLORS.carrying;
      context.stroke();
    }
  });
}

function eventLogItem(event) {
  const item = document.createElement('li');
  item.dataset.kind = event.kind;
  const step = document.createElement('span');
  step.className = 'event-step';
  step.textContent = `Step ${event.step.toLocaleString()}`;
  const title = document.createElement('strong');
  title.textContent = event.title;
  const detail = document.createElement('span');
  detail.className = 'event-detail';
  detail.textContent = event.detail;
  item.append(step, title, detail);
  return item;
}

function renderEventLog(currentStep) {
  const visibleEvents = (currentTrace?.events || []).filter((event) => event.step <= currentStep);
  if (visibleEvents.length === renderedEventCount) return;

  if (!visibleEvents.length) {
    const empty = document.createElement('li');
    empty.className = 'muted';
    empty.textContent = 'No significant event has occurred yet.';
    eventLog.replaceChildren(empty);
  } else if (renderedEventCount >= 0 && visibleEvents.length > renderedEventCount) {
    if (renderedEventCount === 0) eventLog.replaceChildren();
    visibleEvents.slice(renderedEventCount).forEach((event) => {
      eventLog.append(eventLogItem(event));
    });
  } else {
    eventLog.replaceChildren(...visibleEvents.map(eventLogItem));
  }
  renderedEventCount = visibleEvents.length;
  eventLog.scrollTop = eventLog.scrollHeight;
}

function renderCurrentFrame() {
  if (!currentTrace || !currentTrace.frames.length) return;
  const frame = currentTrace.frames[currentFrameIndex];
  drawSimulation(frame);
  stepValue.textContent = frame.step.toLocaleString();
  timeline.value = String(currentFrameIndex);
  updateMetrics(frame);
  renderEventLog(frame.step);
}

function updateMetrics(frame) {
  document.querySelector('#metric-nest').textContent = frame.nest_food.toLocaleString();
  document.querySelector('#metric-carrying').textContent = frame.carried_food.toLocaleString();
  document.querySelector('#metric-uncommitted').textContent = (frame.commitment_counts.uncommitted || 0).toLocaleString();
  document.querySelector('#metric-reason').textContent =
    currentFrameIndex === currentTrace.frames.length - 1
      ? currentTrace.result.reason.replaceAll('_', ' ')
      : 'in progress';

  const container = document.querySelector('#allocation-bars');
  container.replaceChildren();
  const total = currentTrace.config.ant_count;
  Object.entries(frame.commitment_counts).forEach(([key, count]) => {
    const row = document.createElement('div');
    row.className = 'allocation-row';
    const label = document.createElement('div');
    label.className = 'allocation-label';
    const name = document.createElement('span');
    name.textContent = key === 'uncommitted' ? 'Uncommitted' : `Feeder ${key}`;
    const value = document.createElement('span');
    value.textContent = `${count} · ${Math.round((count / total) * 100)}%`;
    label.append(name, value);
    const track = document.createElement('div');
    track.className = 'allocation-track';
    const fill = document.createElement('div');
    fill.className = 'allocation-fill';
    fill.dataset.feeder = key;
    fill.style.width = `${(count / total) * 100}%`;
    track.append(fill);
    row.append(label, track);
    container.append(row);
  });
}

function svgElement(name, attributes = {}) {
  const element = document.createElementNS('http://www.w3.org/2000/svg', name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  return element;
}

function renderChart() {
  if (!currentTrace) return;
  chart.replaceChildren();
  chartEmpty.hidden = true;
  const width = 900;
  const height = 270;
  const margin = { left: 52, right: 18, top: 18, bottom: 32 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  chart.setAttribute('viewBox', `0 0 ${width} ${height}`);

  const frames = currentTrace.frames;
  const maxStep = Math.max(1, currentTrace.result.steps);
  const initialFood = currentTrace.config.feeders.reduce((sum, feeder) => sum + feeder.food, 0);
  const maxFood = Math.max(1, initialFood);
  const x = (step) => margin.left + (step / maxStep) * plotWidth;
  const y = (value) => margin.top + plotHeight - (value / maxFood) * plotHeight;

  for (let index = 0; index <= 4; index += 1) {
    const value = Math.round((maxFood * index) / 4);
    const lineY = y(value);
    chart.append(svgElement('line', { x1: margin.left, x2: width - margin.right, y1: lineY, y2: lineY, class: 'chart-grid' }));
    const label = svgElement('text', { x: margin.left - 8, y: lineY + 4, 'text-anchor': 'end', class: 'chart-axis' });
    label.textContent = value.toLocaleString();
    chart.append(label);
  }

  [0, .25, .5, .75, 1].forEach((fraction) => {
    const value = Math.round(maxStep * fraction);
    const label = svgElement('text', { x: x(value), y: height - 9, 'text-anchor': 'middle', class: 'chart-axis' });
    label.textContent = value.toLocaleString();
    chart.append(label);
  });

  const series = [
    { key: 'nest', values: frames.map((frame) => frame.nest_food) },
    ...currentTrace.config.feeders.map((feeder) => ({
      key: feeder.feeder_id,
      values: frames.map((frame) => frame.feeder_food[feeder.feeder_id]),
    })),
  ];

  series.forEach((item) => {
    const points = frames.map((frame, index) => `${x(frame.step)},${y(item.values[index])}`).join(' ');
    chart.append(svgElement('polyline', { points, class: `chart-line ${item.key}` }));
  });
}

function startPlayback() {
  if (!currentTrace) return;
  if (currentFrameIndex >= currentTrace.frames.length - 1) currentFrameIndex = 0;
  playButton.textContent = 'Pause';
  const speed = Number(playbackSpeed.value);
  playbackTimer = window.setInterval(() => {
    currentFrameIndex += 1;
    renderCurrentFrame();
    if (currentFrameIndex >= currentTrace.frames.length - 1) stopPlayback();
  }, Math.max(35, 1000 / speed));
}

function stopPlayback() {
  if (playbackTimer !== null) window.clearInterval(playbackTimer);
  playbackTimer = null;
  playButton.textContent = 'Play';
}

function togglePlayback() {
  if (playbackTimer === null) startPlayback();
  else stopPlayback();
}

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem('ant-foraging-run-history') || '[]');
  } catch {
    return [];
  }
}

function recordRun(trace) {
  const summary = {
    seed: trace.result.seed,
    steps: trace.result.steps,
    reason: trace.result.reason,
    nest_food: trace.result.nest_food,
    carried_food: trace.result.carried_food,
    recorded_at: new Date().toISOString(),
  };
  runHistory = [summary, ...runHistory].slice(0, 50);
  localStorage.setItem('ant-foraging-run-history', JSON.stringify(runHistory));
  renderHistory();
}

function renderHistory() {
  historyBody.replaceChildren();
  if (!runHistory.length) {
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    cell.colSpan = 6;
    cell.className = 'empty-cell';
    cell.textContent = 'No recorded runs in this browser.';
    row.append(cell);
    historyBody.append(row);
    document.querySelector('#export-csv').disabled = true;
    return;
  }

  runHistory.forEach((run) => {
    const row = document.createElement('tr');
    [
      run.seed,
      run.steps,
      run.reason.replaceAll('_', ' '),
      run.nest_food,
      run.carried_food,
      new Date(run.recorded_at).toLocaleString(),
    ].forEach((value) => {
      const cell = document.createElement('td');
      cell.textContent = typeof value === 'number' ? value.toLocaleString() : value;
      row.append(cell);
    });
    historyBody.append(row);
  });
  document.querySelector('#export-csv').disabled = false;
}

function downloadFile(filename, content, type) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function exportJson() {
  if (!currentTrace) return;
  downloadFile(`ant-run-seed-${currentTrace.result.seed}.json`, JSON.stringify(currentTrace, null, 2), 'application/json');
}

function csvCell(value) {
  return `"${String(value).replaceAll('"', '""')}"`;
}

function exportCsv() {
  if (!runHistory.length) return;
  const columns = ['seed', 'steps', 'reason', 'nest_food', 'carried_food', 'recorded_at'];
  const rows = [columns.join(','), ...runHistory.map((run) => columns.map((column) => csvCell(run[column])).join(','))];
  downloadFile('ant-foraging-run-history.csv', rows.join('\n'), 'text/csv');
}

async function checkHealth() {
  try {
    const response = await fetch('/api/health');
    if (!response.ok) throw new Error();
    apiIndicator.classList.add('is-online');
    apiIndicator.title = 'Simulation API online';
    apiStatus.textContent = 'Simulation API online.';
  } catch {
    apiIndicator.classList.add('is-error');
    apiIndicator.title = 'Simulation API unavailable';
    apiStatus.textContent = 'Simulation API unavailable.';
  }
}

const feederTabs = [...document.querySelectorAll('.feeder-tab')];

function activateFeederTab(tab) {
  feederTabs.forEach((item) => {
    const active = item === tab;
    item.classList.toggle('is-active', active);
    item.setAttribute('aria-selected', String(active));
    item.tabIndex = active ? 0 : -1;
  });
  document.querySelectorAll('.feeder-form').forEach((panel) => {
    const active = panel.dataset.feederForm === tab.dataset.feederTab;
    panel.classList.toggle('is-active', active);
    panel.hidden = !active;
  });
}

feederTabs.forEach((tab, index) => {
  tab.addEventListener('click', () => activateFeederTab(tab));
  tab.addEventListener('keydown', (event) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    let nextIndex = index;
    if (event.key === 'ArrowLeft') nextIndex = (index - 1 + feederTabs.length) % feederTabs.length;
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % feederTabs.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = feederTabs.length - 1;
    activateFeederTab(feederTabs[nextIndex]);
    feederTabs[nextIndex].focus();
  });
});

form.addEventListener('submit', runExperiment);
presetSelect.addEventListener('change', () => applyPreset(presetSelect.value));
form.addEventListener('input', (event) => {
  if (event.target === presetSelect) return;
  presetSelect.value = 'custom';
  applyPreset('custom');
});
playButton.addEventListener('click', togglePlayback);
timeline.addEventListener('input', () => {
  stopPlayback();
  currentFrameIndex = Number(timeline.value);
  renderCurrentFrame();
});
playbackSpeed.addEventListener('change', () => {
  if (playbackTimer !== null) {
    stopPlayback();
    startPlayback();
  }
});
document.querySelector('#export-json').addEventListener('click', exportJson);
document.querySelector('#export-csv').addEventListener('click', exportCsv);
document.querySelector('#clear-history').addEventListener('click', () => {
  runHistory = [];
  localStorage.removeItem('ant-foraging-run-history');
  renderHistory();
});

new ResizeObserver(resizeCanvas).observe(canvas.parentElement);
window.addEventListener('beforeunload', stopPlayback);
applyPreset(presetSelect.value);
renderHistory();
checkHealth();
