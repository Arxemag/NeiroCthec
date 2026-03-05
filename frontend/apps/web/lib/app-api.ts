/**
 * Клиент для Python App API (порт 8000).
 * Все запросы требуют заголовок X-User-Id.
 * Базовый URL задаётся через NEXT_PUBLIC_APP_API_URL (по умолчанию http://localhost:8000 для разработки).
 */

import { getStoredUserId } from './auth';

const APP_API_BASE =
  (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_APP_API_URL?.trim()) ||
  (typeof window !== 'undefined' ? 'http://localhost:8000' : '');

export function getAppApiUrl(): string {
  return APP_API_BASE.replace(/\/$/, '');
}

export function isAppApiEnabled(): boolean {
  return Boolean(APP_API_BASE?.trim());
}

function getAppHeaders(init?: RequestInit): Headers {
  const headers = new Headers(init?.headers);
  const userId =
    getStoredUserId() ??
    (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_DEV_USER_ID) ??
    'anonymous';
  headers.set('X-User-Id', typeof userId === 'string' && userId.trim() ? userId.trim() : 'anonymous');
  return headers;
}

/** GET/POST к app без JSON body (для JSON body используйте appJson). */
export async function appFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const base = getAppApiUrl();
  if (!base) {
    throw new Error(
      'App API недоступен: задайте NEXT_PUBLIC_APP_API_URL в .env (например http://localhost:8000) или запустите Core API на порту 8000.',
    );
  }
  const headers = getAppHeaders(init);
  if (typeof init.body === 'string' && init.body.length > 0) {
    headers.set('Content-Type', 'application/json');
  }
  const url = `${base}${path.startsWith('/') ? path : `/${path}`}`;
  let res: Response;
  try {
    res = await fetch(url, { ...init, headers, credentials: 'include' });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    throw new Error(
      `Не удалось подключиться к App API (${base}). Запустите сервер (python main.py в папке app) или проверьте сеть. Ошибка: ${msg}`,
    );
  }
  return res;
}

/** GET с парсингом JSON; при !res.ok бросает Error с detail из тела. */
export async function appJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await appFetch(path, init);
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    if (!res.ok) throw new Error(text || `HTTP ${res.status}`);
  }
  if (!res.ok) {
    const obj = data && typeof data === 'object' ? (data as Record<string, unknown>) : {};
    const message = (typeof (obj as { detail?: string }).detail === 'string'
      ? (obj as { detail: string }).detail
      : null) ?? (text || `HTTP ${res.status}`);
    throw new Error(message);
  }
  return data as T;
}

// --- Типы ответов App API (совпадают с docs/APP_API_FRONTEND.md) ---

export type AppBook = {
  id: string;
  title: string;
  status: string;
  created_at: string;
  final_audio_path: string | null;
};

export type AppBookUploadResponse = { id: string; status: string };

export type AppBookStatusResponse = {
  stage: string;
  progress: number;
  total_lines: number;
  tts_done: number;
};

export type AppProcessBookStage4Response = {
  book_id: string;
  processed_tasks: number;
  remaining_tasks: number;
  book_status: string;
  final_audio_path: string | null;
  stopped: boolean;
};

/** POST /books/upload — загрузка файла .txt, .fb2, .epub, .mobi */
export async function uploadBook(file: File): Promise<AppBookUploadResponse> {
  const base = getAppApiUrl();
  if (!base) throw new Error('NEXT_PUBLIC_APP_API_URL is not set');
  const formData = new FormData();
  formData.append('file', file);
  const headers = getAppHeaders({ method: 'POST' });
  headers.delete('Content-Type');
  const res = await fetch(`${base}/api/books/upload`, {
    method: 'POST',
    headers,
    body: formData,
    credentials: 'include',
  });
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    if (!res.ok) throw new Error(text || `HTTP ${res.status}`);
  }
  if (!res.ok) {
    const obj = data && typeof data === 'object' ? (data as Record<string, unknown>) : {};
    const message = (typeof (obj as { detail?: string }).detail === 'string' ? (obj as { detail: string }).detail : null) ?? (text || `HTTP ${res.status}`);
    throw new Error(message);
  }
  return data as AppBookUploadResponse;
}

/** GET /books — список книг пользователя */
export async function listBooks(): Promise<AppBook[]> {
  return appJson<AppBook[]>('/books');
}

/** GET /books?project_id=... — книги, привязанные к проекту (уже загруженный текст без повторной загрузки). */
export async function listBooksByProject(projectId: string): Promise<AppBook[]> {
  const q = new URLSearchParams({ project_id: projectId });
  return appJson<AppBook[]>(`/books?${q.toString()}`);
}

/** GET /books/:id — одна книга */
export async function getBook(bookId: string): Promise<AppBook> {
  return appJson<AppBook>(`/books/${encodeURIComponent(bookId)}`);
}

/** GET /books/:id/status — прогресс TTS */
export async function getBookStatus(bookId: string): Promise<AppBookStatusResponse> {
  return appJson<AppBookStatusResponse>(`/books/${encodeURIComponent(bookId)}/status`);
}

/** DELETE /api/books/:id — удалить книгу с сервера */
export async function deleteBook(bookId: string): Promise<{ status: string; book_id: string }> {
  return appJson<{ status: string; book_id: string }>(`/api/books/${encodeURIComponent(bookId)}`, { method: 'DELETE' });
}

/** DELETE /api/books/by-project/:projectId — удалить все книги, привязанные к проекту (вызывать перед удалением проекта в Nest). */
export async function deleteBooksByProject(projectId: string): Promise<{ status: string; deleted_count: number; book_ids: string[] }> {
  return appJson<{ status: string; deleted_count: number; book_ids: string[] }>(
    `/api/books/by-project/${encodeURIComponent(projectId)}`,
    { method: 'DELETE' },
  );
}

/**
 * Скачать аудио: GET /books/:id/download с X-User-Id.
 * Возвращает blob и предлагаемое имя файла (без пути).
 */
export async function downloadBookAudio(bookId: string): Promise<{ blob: Blob; filename: string }> {
  const res = await appFetch(`/books/${encodeURIComponent(bookId)}/download`);
  if (!res.ok) {
    const text = await res.text();
    let msg = text;
    try {
      const j = JSON.parse(text) as { detail?: string };
      if (typeof j.detail === 'string') msg = j.detail;
    } catch {}
    throw new Error(msg || `HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const disposition = res.headers.get('Content-Disposition');
  let filename = `${bookId}.wav`;
  if (disposition) {
    const m = disposition.match(/filename="?([^";\n]+)"?/);
    if (m) filename = m[1].trim();
  }
  return { blob, filename };
}

/** Сохранить выбор голосов в настройках пользователя (GET + merge + PUT /books/settings/audio). Тогда и process-book-stage4, и tts-next будут использовать эти голоса. */
export async function putAudioConfigVoiceIds(voiceIds: {
  narrator?: string;
  male?: string;
  female?: string;
}): Promise<void> {
  if (!voiceIds.narrator && !voiceIds.male && !voiceIds.female) return;
  type AudioConfigRes = { config?: Record<string, unknown> };
  const current = await appJson<AudioConfigRes>('/books/settings/audio').catch(() => ({ config: {} }));
  const config = { ...(current?.config && typeof current.config === 'object' ? current.config : {}), voice_ids: { ...(voiceIds.narrator && { narrator: voiceIds.narrator }), ...(voiceIds.male && { male: voiceIds.male }), ...(voiceIds.female && { female: voiceIds.female }) } };
  await appJson<unknown>('/books/settings/audio', { method: 'PUT', body: JSON.stringify({ config }) });
}

/** POST /internal/process-book-stage4 — запустить озвучку (до max_tasks строк). voice_ids из запроса имеют приоритет над дефолтами. */
export async function processBookStage4(
  bookId: string,
  maxTasks = 500,
  voiceIds?: { narrator?: string; male?: string; female?: string }
): Promise<AppProcessBookStage4Response> {
  const body: { book_id: string; max_tasks: number; voice_ids?: Record<string, string> } = {
    book_id: bookId,
    max_tasks: maxTasks,
  };
  if (voiceIds && (voiceIds.narrator || voiceIds.male || voiceIds.female)) {
    body.voice_ids = {};
    if (voiceIds.narrator) body.voice_ids.narrator = voiceIds.narrator;
    if (voiceIds.male) body.voice_ids.male = voiceIds.male;
    if (voiceIds.female) body.voice_ids.female = voiceIds.female;
  }
  return appJson<AppProcessBookStage4Response>('/internal/process-book-stage4', {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/** POST /internal/stop-book-stage4 — запрос остановки озвучки книги */
export async function stopBookStage4(bookId: string): Promise<{ book_id: string; stop_requested: boolean }> {
  return appJson<{ book_id: string; stop_requested: boolean }>('/internal/stop-book-stage4', {
    method: 'POST',
    body: JSON.stringify({ book_id: bookId }),
  });
}

// --- Голоса (список + сэмплы для прослушивания) ---

export type AppVoice = {
  id: string;
  name: string;
  role: 'narrator' | 'male' | 'female';
  sample_url: string;
};

/** GET /voices — список доступных голосов с ролями (диктор, мужской, женский) и URL сэмплов */
export async function listVoices(): Promise<AppVoice[]> {
  return appJson<AppVoice[]>('/voices');
}

/** Полный URL для проигрывания сэмпла голоса (для <audio src={...} /> или fetch). */
export function getVoiceSampleUrl(voiceId: string): string {
  const base = getAppApiUrl();
  if (!base) return '';
  return `${base}/voices/${encodeURIComponent(voiceId)}/sample`;
}
