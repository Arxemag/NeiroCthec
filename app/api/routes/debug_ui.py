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
    input, button, textarea { font-size: 14px; padding: 8px; }
    input { min-width: 240px; }
    textarea { width: 100%; min-height: 160px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    .ok { color: #0a7a2b; }
    .bad { color: #b30000; }
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
      <input id=\"bookFile\" type=\"file\" />
      <button onclick=\"uploadBook()\">POST /books/upload</button>
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
      <input id=\"lineId\" placeholder=\"line_id\" />
      <input id=\"audioPath\" placeholder=\"audio_path (например s3://audio/...)\" />
      <button onclick=\"completeTask()\">POST /internal/tts-complete</button>
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
