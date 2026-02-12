from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/ui", response_class=HTMLResponse)
def debug_ui() -> str:
    return """<!doctype html>
<html lang=\"ru\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>NeiroCthec API Test UI</title>
  <style>
    body { font-family: Inter, Arial, sans-serif; max-width: 980px; margin: 24px auto; padding: 0 16px; }
    h1 { font-size: 24px; margin-bottom: 4px; }
    .muted { color: #666; margin-bottom: 20px; }
    .card { border: 1px solid #ddd; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 20px; }
    .range-wrap { display: grid; grid-template-columns: 220px 1fr 70px; align-items: center; gap: 8px; }
    .range-wrap input[type=range] { width: 100%; }
    input, button, textarea { font-size: 14px; padding: 8px; }
    input { min-width: 240px; }
    textarea { width: 100%; min-height: 160px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .ok { color: #0a7a2b; }
    .bad { color: #b30000; }
    .progress { width: 100%; height: 18px; background:#eee; border-radius: 999px; overflow:hidden; margin-top:8px; }
    .bar { height:100%; width:0%; background:#3b82f6; transition: width .25s; }
  </style>
</head>
<body>
  <h1>NeiroCthec API Test UI</h1>
  <div class=\"muted\">Быстрая ручная проверка эндпоинтов без Postman.</div>

  <div class=\"card\">
    <div class=\"row\">
      <label for=\"userId\">X-User-Id</label>
      <input id=\"userId\" value=\"demo-user\" />
      <button onclick=\"saveUser()\">Сохранить</button>
      <span id=\"userSaved\" class=\"muted\"></span>
    </div>
  </div>

  <div class=\"card\">
    <h3>1) Upload книги</h3>
    <div class=\"row\">
      <input id=\"bookFile\" type=\"file\" accept=\".txt,.fb2,text/plain,application/xml\" />
      <button onclick=\"uploadBook()\">POST /books/upload</button>
      <button onclick=\"uploadAndRunFullPipeline()\">Upload + Stage4/5</button>
    </div>
  </div>

  <div class=\"card\">
    <h3>2) Получение списка/карточки/статуса</h3>
    <div class=\"row\">
      <button onclick=\"listBooks()\">GET /books</button>
      <input id=\"bookId\" placeholder=\"book_id\" />
      <button onclick=\"getBook()\">GET /books/{id}</button>
      <button onclick=\"getStatus()\">GET /books/{id}/status</button>
      <button onclick=\"downloadBook()\">GET /books/{id}/download</button>
    </div>
  </div>

  <div class=\"card\">
    <h3>3) Внутренние endpoints Stage4</h3>
    <div class=\"row\">
      <button onclick=\"leaseTask()\">POST /internal/tts-next</button>
      <button onclick=\"runStage4ForBook()\">POST /internal/process-book-stage4</button>
      <button onclick=\"stopStage4ForBook()\">STOP Stage4</button>
      <input id=\"lineId\" placeholder=\"line_id\" />
      <input id=\"audioPath\" placeholder=\"audio_path (например s3://audio/...)\" />
      <button onclick=\"completeTask()\">POST /internal/tts-complete</button>
    </div>
    <div class="muted" id="stage4ProgressText">Stage4 progress: 0%</div>
    <div class="progress"><div id="stage4ProgressBar" class="bar"></div></div>

  </div>

  <div class="card">
    <h3>4) Быстрая настройка TTS (audio.yaml)</h3>
    <div class="muted">Читает/сохраняет через `/books/settings/audio` для текущего `X-User-Id`.</div>
    <div class="grid2">
      <div class="range-wrap"><label for="xtts_temperature">xtts.temperature</label><input type="range" id="xtts_temperature" min="0.1" max="2.0" step="0.05" oninput="syncRangeValue('xtts_temperature')" /><span id="xtts_temperature_val"></span></div>
      <div class="range-wrap"><label for="xtts_top_k">xtts.top_k</label><input type="range" id="xtts_top_k" min="1" max="200" step="1" oninput="syncRangeValue('xtts_top_k')" /><span id="xtts_top_k_val"></span></div>
      <div class="range-wrap"><label for="xtts_top_p">xtts.top_p</label><input type="range" id="xtts_top_p" min="0.1" max="1.0" step="0.01" oninput="syncRangeValue('xtts_top_p')" /><span id="xtts_top_p_val"></span></div>
      <div class="range-wrap"><label for="xtts_repetition_penalty">xtts.repetition_penalty</label><input type="range" id="xtts_repetition_penalty" min="1.0" max="5.0" step="0.1" oninput="syncRangeValue('xtts_repetition_penalty')" /><span id="xtts_repetition_penalty_val"></span></div>
      <div class="range-wrap"><label for="xtts_speed_base">xtts.speed_base</label><input type="range" id="xtts_speed_base" min="0.5" max="1.8" step="0.01" oninput="syncRangeValue('xtts_speed_base')" /><span id="xtts_speed_base_val"></span></div>
      <div class="range-wrap"><label for="pauses_line_pause_ms">pauses.line_pause_ms</label><input type="range" id="pauses_line_pause_ms" min="0" max="2000" step="50" oninput="syncRangeValue('pauses_line_pause_ms')" /><span id="pauses_line_pause_ms_val"></span></div>
      <div class="range-wrap"><label for="pauses_max_pause_ms">pauses.max_pause_ms</label><input type="range" id="pauses_max_pause_ms" min="200" max="5000" step="50" oninput="syncRangeValue('pauses_max_pause_ms')" /><span id="pauses_max_pause_ms_val"></span></div>
    </div>
    <div class="row" style="margin-top: 10px;">
      <button onclick="loadAudioSettings()">Загрузить настройки</button>
      <button onclick="saveAudioSettings()">Сохранить настройки</button>
      <button onclick="resetAudioSettings()">Сбросить на глобальные</button>
    </div>
  </div>

<div class=\"card\">
    <h3>Лог</h3>
    <textarea id=\"log\" readonly></textarea>
  </div>

<script>
const $ = (id) => document.getElementById(id);
const log = (title, payload, ok = true) => {
  const row = `[${new Date().toLocaleTimeString()}] ${title}\n${typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2)}\n\n`;
  $("log").value = row + $("log").value;
  $("log").className = ok ? 'ok' : 'bad';
};

const getUserId = () => localStorage.getItem('nc_user_id') || 'demo-user';
const headers = (extra = {}) => ({ 'X-User-Id': getUserId(), ...extra });

(function init(){
  $("userId").value = getUserId();
  setDefaultRanges();
  loadAudioSettings();
  refreshStage4Progress();
})();

function saveUser(){
  localStorage.setItem('nc_user_id', $("userId").value.trim() || 'demo-user');
  $("userSaved").textContent = 'сохранено';
  setTimeout(() => $("userSaved").textContent = '', 1200);
}

async function parseResponse(res){
  const type = res.headers.get('content-type') || '';
  if (type.includes('application/json')) return await res.json();
  return await res.text();
}


const RANGE_FIELDS = [
  'xtts_temperature',
  'xtts_top_k',
  'xtts_top_p',
  'xtts_repetition_penalty',
  'xtts_speed_base',
  'pauses_line_pause_ms',
  'pauses_max_pause_ms',
];

function syncRangeValue(id){
  const el = $(id);
  const v = el ? el.value : '';
  const out = $(id + '_val');
  if (out) out.textContent = v;
}

function setDefaultRanges(){
  const defaults = {
    xtts_temperature: 1.0,
    xtts_top_k: 50,
    xtts_top_p: 1.0,
    xtts_repetition_penalty: 2.8,
    xtts_speed_base: 1.2,
    pauses_line_pause_ms: 500,
    pauses_max_pause_ms: 2500,
  };
  for (const [k,v] of Object.entries(defaults)){
    if ($(k)) $(k).value = v;
    syncRangeValue(k);
  }
}

function applyAudioConfigToSliders(config){
  const xtts = config?.xtts || {};
  const pauses = config?.pauses || {};
  const mapping = {
    xtts_temperature: xtts.temperature,
    xtts_top_k: xtts.top_k,
    xtts_top_p: xtts.top_p,
    xtts_repetition_penalty: xtts.repetition_penalty,
    xtts_speed_base: xtts.speed_base,
    pauses_line_pause_ms: pauses.line_pause_ms,
    pauses_max_pause_ms: pauses.max_pause_ms,
  };
  for (const [id,val] of Object.entries(mapping)){
    if (val !== undefined && $(id)) $(id).value = val;
    syncRangeValue(id);
  }
}

function buildAudioConfigFromSliders(){
  return {
    xtts: {
      temperature: parseFloat($('xtts_temperature').value),
      top_k: parseInt($('xtts_top_k').value, 10),
      top_p: parseFloat($('xtts_top_p').value),
      repetition_penalty: parseFloat($('xtts_repetition_penalty').value),
      speed_base: parseFloat($('xtts_speed_base').value),
    },
    pauses: {
      line_pause_ms: parseInt($('pauses_line_pause_ms').value, 10),
      max_pause_ms: parseInt($('pauses_max_pause_ms').value, 10),
    }
  };
}

async function loadAudioSettings(){
  const res = await fetch('/books/settings/audio', { headers: headers() });
  const body = await parseResponse(res);
  log('GET /books/settings/audio', body, res.ok);
  if (res.ok) applyAudioConfigToSliders(body.config || {});
}

async function saveAudioSettings(){
  const config = buildAudioConfigFromSliders();
  const res = await fetch('/books/settings/audio', {
    method: 'PUT',
    headers: { ...headers(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ config })
  });
  const body = await parseResponse(res);
  log('PUT /books/settings/audio', body, res.ok);
}

async function resetAudioSettings(){
  const res = await fetch('/books/settings/audio', { method: 'DELETE', headers: headers() });
  const body = await parseResponse(res);
  log('DELETE /books/settings/audio', body, res.ok);
  if (res.ok) applyAudioConfigToSliders(body.config || {});
}


let stage4PollTimer = null;
let stage4StopRequested = false;

function setStage4Progress(progress, done, total){
  const pct = Math.max(0, Math.min(100, Number(progress || 0)));
  if ($('stage4ProgressBar')) $('stage4ProgressBar').style.width = pct + '%';
  if ($('stage4ProgressText')) $('stage4ProgressText').textContent = `Stage4 progress: ${pct}% (${done || 0}/${total || 0})`;
}

async function refreshStage4Progress(){
  const id = $('bookId').value.trim();
  if (!id) return;
  const res = await fetch(`/books/${id}/status`, { headers: headers() });
  const body = await parseResponse(res);
  if (res.ok) setStage4Progress(body.progress, body.tts_done, body.total_lines);
}

function startStage4Polling(){
  if (stage4PollTimer) clearInterval(stage4PollTimer);
  stage4PollTimer = setInterval(refreshStage4Progress, 1500);
}
function stopStage4Polling(){
  if (stage4PollTimer) clearInterval(stage4PollTimer);
  stage4PollTimer = null;
}

async function stopStage4ForBook(){
  const id = $('bookId').value.trim();
  if (!id) return log('stop stage4: ошибка', 'Нужен book_id', false);
  stage4StopRequested = true;
  const res = await fetch('/internal/stop-book-stage4', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ book_id: id })
  });
  log('POST /internal/stop-book-stage4', await parseResponse(res), res.ok);
}

async function uploadBook(){
  const file = $("bookFile").files[0];
  if (!file) return log('upload: ошибка', 'Выбери файл', false);
  const fd = new FormData();
  fd.append('file', file);
  const res = await fetch('/books/upload', { method: 'POST', headers: headers(), body: fd });
  const body = await parseResponse(res);
  log('POST /books/upload', body, res.ok);
  if (res.ok && body.id) $("bookId").value = body.id;
}

async function listBooks(){
  const res = await fetch('/books', { headers: headers() });
  log('GET /books', await parseResponse(res), res.ok);
}

async function getBook(){
  const id = $("bookId").value.trim();
  if (!id) return log('get book: ошибка', 'Нужен book_id', false);
  const res = await fetch(`/books/${id}`, { headers: headers() });
  log('GET /books/{id}', await parseResponse(res), res.ok);
}

async function getStatus(){
  const id = $("bookId").value.trim();
  if (!id) return log('status: ошибка', 'Нужен book_id', false);
  const res = await fetch(`/books/${id}/status`, { headers: headers() });
  log('GET /books/{id}/status', await parseResponse(res), res.ok);
}

async function downloadBook(){
  const id = $("bookId").value.trim();
  if (!id) return log('download: ошибка', 'Нужен book_id', false);
  const res = await fetch(`/books/${id}/download`, { headers: headers() });
  if (!res.ok) return log('GET /books/{id}/download', await parseResponse(res), false);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${id}.mp3`;
  a.click();
  URL.revokeObjectURL(url);
  log('GET /books/{id}/download', `Скачано: ${blob.size} bytes`, true);
}


async function runStage4ForBook(){
  const id = $("bookId").value.trim();
  if (!id) return log('stage4: ошибка', 'Нужен book_id', false);
  stage4StopRequested = false;
  startStage4Polling();

  let last = null;
  while (!stage4StopRequested) {
    const res = await fetch('/internal/process-book-stage4', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ book_id: id, max_tasks: 5 })
    });
    const body = await parseResponse(res);
    log('POST /internal/process-book-stage4', body, res.ok);
    if (!res.ok) { stopStage4Polling(); return null; }
    last = body;
    await refreshStage4Progress();
    if (body.stopped || body.remaining_tasks === 0 || body.book_status === 'completed') break;
  }

  stopStage4Polling();
  return last;
}

async function uploadAndRunFullPipeline(){
  await uploadBook();
  const id = $("bookId").value.trim();
  if (!id) return;
  const result = await runStage4ForBook();
  if (result) await getStatus();
}
async function leaseTask(){
  const res = await fetch('/internal/tts-next', { method: 'POST' });
  const body = await parseResponse(res);
  log('POST /internal/tts-next', body, res.ok);
  if (res.ok && body.line_id) $("lineId").value = body.line_id;
}

async function completeTask(){
  const lineId = $("lineId").value.trim();
  const audioPath = $("audioPath").value.trim();
  if (!lineId || !audioPath) return log('tts-complete: ошибка', 'Нужны line_id и audio_path', false);
  const res = await fetch('/internal/tts-complete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ line_id: lineId, audio_path: audioPath })
  });
  log('POST /internal/tts-complete', await parseResponse(res), res.ok);
}
</script>
</body>
</html>
"""
