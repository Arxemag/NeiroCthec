/**
 * Клиент для Python App API (порт 8000).
 * Все запросы требуют заголовок X-User-Id.
 * Базовый URL задаётся через NEXT_PUBLIC_APP_API_URL.
 * Варианты:
 * - http://localhost:8000 — прямое обращение к Core (для локальной разработки).
 * - proxy — запросы идут на тот же хост через /app-api (Next.js проксирует на Core); удобно в Docker при доступе по IP.
 */

import { getStoredUserId } from './auth';

const RAW = (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_APP_API_URL?.trim()) || '';
const USE_PROXY = RAW.toLowerCase() === 'proxy';
const APP_API_BASE = USE_PROXY ? '' : (RAW || (typeof window !== 'undefined' ? 'http://localhost:8000' : ''));

const APP_API_PROXY_PREFIX = '/app-api';

export function getAppApiUrl(): string {
  if (USE_PROXY) return '';
  return (APP_API_BASE as string).replace(/\/$/, '');
}

export function isAppApiEnabled(): boolean {
  return USE_PROXY || Boolean((APP_API_BASE as string)?.trim());
}

/** URL сэмпла голоса для <audio src> (через прокси или прямой Core). */
export function getAppApiVoiceSampleUrl(voiceId: string): string {
  if (USE_PROXY && typeof window !== 'undefined') {
    return `${window.location.origin}${APP_API_PROXY_PREFIX}/voices/${encodeURIComponent(voiceId)}/sample`;
  }
  const base = getAppApiUrl();
  return base ? `${base.replace(/\/$/, '')}/voices/${encodeURIComponent(voiceId)}/sample` : '';
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
  const pathNorm = path.startsWith('/') ? path : `/${path}`;
  const url = USE_PROXY ? `${APP_API_PROXY_PREFIX}${pathNorm}` : `${base}${pathNorm}`;
  if (!USE_PROXY && !base) {
    throw new Error(
      'App API недоступен: задайте NEXT_PUBLIC_APP_API_URL в .env (например http://localhost:8000 или proxy) или запустите Core API на порту 8000.',
    );
  }
  const headers = getAppHeaders(init);
  if (typeof init.body === 'string' && init.body.length > 0) {
    headers.set('Content-Type', 'application/json');
  }
  let res: Response;
  try {
    res = await fetch(url, { ...init, headers, credentials: 'include' });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    const hint = USE_PROXY
      ? 'Проверьте, что Core запущен и Next.js проксирует /app-api на него (APP_API_PROXY_TARGET).'
      : `Запустите Core (python main.py в папке app) или при доступе по IP задайте NEXT_PUBLIC_APP_API_URL=proxy.`;
    throw new Error(`Не удалось подключиться к App API. ${hint} Ошибка: ${msg}`);
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
  /** Номера глав, у которых все строки озвучены (для раннего воспроизведения). */
  chapters_ready?: number[];
};

export type AppProcessBookStage4Response = {
  book_id: string;
  processed_tasks: number;
  remaining_tasks: number;
  book_status: string;
  final_audio_path: string | null;
  stopped: boolean;
  /** true, если все строки уже озвучены и в очередь ничего не добавлено */
  all_lines_done?: boolean;
};

/** POST загрузка книги: при proxy — /upload-book (Next route), иначе Core /api/books/upload */
export async function uploadBook(file: File): Promise<AppBookUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const headers = getAppHeaders({ method: 'POST' });
  headers.delete('Content-Type');
  const base = getAppApiUrl();
  const url = USE_PROXY
    ? (typeof window !== 'undefined' ? new URL('/upload-book', window.location.origin).href : '/upload-book')
    : (base || '').replace(/\/$/, '') + '/api/books/upload';
  if (!USE_PROXY && !base) throw new Error('NEXT_PUBLIC_APP_API_URL is not set');
  const res = await fetch(url, {
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

/** URL для проигрывания главы книги (GET /books/:id/chapters/:num). */
export function getBookChapterAudioUrl(bookId: string, chapterNum: number): string {
  if (USE_PROXY && typeof window !== 'undefined') {
    return `${window.location.origin}${APP_API_PROXY_PREFIX}/books/${encodeURIComponent(bookId)}/chapters/${chapterNum}`;
  }
  const base = getAppApiUrl();
  if (!base) return '';
  return `${base}/books/${encodeURIComponent(bookId)}/chapters/${chapterNum}`;
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

/**
 * Стрим финализированной аудиокниги: GET /internal/audiobooks/stream?folder=... с X-User-Id.
 * Используется для книг после «Создать аудиокнигу» (файл в storage/audiobooks).
 */
export async function getAudiobookStreamBlob(folder: string): Promise<{ blob: Blob; filename: string }> {
  const res = await appFetch(
    `/internal/audiobooks/stream?${new URLSearchParams({ folder }).toString()}`
  );
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
  let filename = 'full.wav';
  if (disposition) {
    const m = disposition.match(/filename="?([^";\n]+)"?/);
    if (m) filename = m[1].trim();
  }
  return { blob, filename };
}

export type TtsEngine = 'qwen3' | 'xtts2';

/** Сохранить выбор голосов и/или движка TTS (GET + merge + PUT /books/settings/audio). */
export async function putAudioConfigVoiceIds(
  voiceIds: { narrator?: string; male?: string; female?: string },
  options?: { ttsEngine?: TtsEngine }
): Promise<void> {
  type AudioConfigRes = { config?: Record<string, unknown> };
  const current = await appJson<AudioConfigRes>('/books/settings/audio').catch(() => ({ config: {} }));
  const config: Record<string, unknown> = { ...(current?.config && typeof current.config === 'object' ? current.config : {}) };
  if (voiceIds.narrator || voiceIds.male || voiceIds.female) {
    config.voice_ids = {
      ...(typeof config.voice_ids === 'object' && config.voice_ids ? config.voice_ids : {}),
      ...(voiceIds.narrator && { narrator: voiceIds.narrator }),
      ...(voiceIds.male && { male: voiceIds.male }),
      ...(voiceIds.female && { female: voiceIds.female }),
    };
  }
  if (options?.ttsEngine !== undefined) config.tts_engine = options.ttsEngine;
  await appJson<unknown>('/books/settings/audio', { method: 'PUT', body: JSON.stringify({ config }) });
}

/** Настройки скорости и тембра по спикеру (narrator, male, female). Передаются в processBookStage4 и при превью. */
export type SpeakerSettings = {
  narrator?: { tempo?: number; pitch?: number };
  male?: { tempo?: number; pitch?: number };
  female?: { tempo?: number; pitch?: number };
};

/** POST /internal/process-book-stage4 — запустить озвучку (до max_tasks строк). voice_ids, tts_engine, speaker_settings, force (игнорировать готовые wav) из запроса. */
export async function processBookStage4(
  bookId: string,
  maxTasks = 500,
  voiceIds?: { narrator?: string; male?: string; female?: string },
  ttsEngine?: TtsEngine,
  speakerSettings?: SpeakerSettings,
  forceReSynthesize?: boolean
): Promise<AppProcessBookStage4Response> {
  const body: {
    book_id: string;
    max_tasks: number;
    voice_ids?: Record<string, string>;
    tts_engine?: TtsEngine;
    speaker_settings?: SpeakerSettings;
    force?: boolean;
  } = {
    book_id: bookId,
    max_tasks: maxTasks,
  };
  if (voiceIds && (voiceIds.narrator || voiceIds.male || voiceIds.female)) {
    body.voice_ids = {};
    if (voiceIds.narrator) body.voice_ids.narrator = voiceIds.narrator;
    if (voiceIds.male) body.voice_ids.male = voiceIds.male;
    if (voiceIds.female) body.voice_ids.female = voiceIds.female;
  }
  if (ttsEngine) body.tts_engine = ttsEngine;
  if (speakerSettings && Object.keys(speakerSettings).length > 0) body.speaker_settings = speakerSettings;
  if (forceReSynthesize) body.force = true;
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

/** GET /voices — список доступных голосов с ролями (диктор, мужской, женский) и URL сэмплов. С X-User-Id Core отдаёт встроенные + свои (storage/voices/{user_id}/*.wav). */
export async function listVoices(): Promise<AppVoice[]> {
  return appJson<AppVoice[]>('/voices');
}

/** POST /voices/upload — загрузить свой голос (WAV). Multipart: file, опционально name, role (narrator|male|female). Заголовок X-User-Id. */
export async function uploadVoice(
  file: File,
  options?: { name?: string; role?: 'narrator' | 'male' | 'female' }
): Promise<{ id: string; name?: string; role?: string }> {
  const formData = new FormData();
  formData.append('file', file);
  if (options?.name?.trim()) formData.append('name', options.name.trim());
  if (options?.role) formData.append('role', options.role);
  const res = await appFetch('/voices/upload', {
    method: 'POST',
    body: formData,
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
    const message =
      (typeof (obj as { detail?: string }).detail === 'string' ? (obj as { detail: string }).detail : null) ??
      (text || `HTTP ${res.status}`);
    throw new Error(message);
  }
  const out = data as { id: string; name?: string; role?: string };
  return { id: out.id, name: out.name, role: out.role };
}

/** DELETE /voices/:id — удалить свой голос. Заголовок X-User-Id. */
export async function deleteVoice(voiceId: string): Promise<void> {
  const res = await appFetch(`/voices/${encodeURIComponent(voiceId)}`, { method: 'DELETE' });
  if (!res.ok) {
    const text = await res.text();
    let msg = text;
    try {
      const j = JSON.parse(text) as { detail?: string };
      if (typeof j.detail === 'string') msg = j.detail;
    } catch {}
    throw new Error(msg || `HTTP ${res.status}`);
  }
}

/** Ответ превью по спикерам: URL аудио для narrator, male, female. */
export type PreviewBySpeakersResponse = {
  narrator?: string;
  male?: string;
  female?: string;
};

/** Базовый URL для запросов к App API (при proxy — origin + /app-api, иначе getAppApiUrl()). */
function getPreviewBaseUrl(): string {
  if (USE_PROXY && typeof window !== 'undefined') {
    return `${window.location.origin}${APP_API_PROXY_PREFIX}`;
  }
  return getAppApiUrl();
}

/**
 * Получить 3 фрагмента превью по спикерам (narrator, male, female).
 * Контракт: POST /internal/preview-by-speakers с book_id, voice_ids, speaker_settings возвращает { narrator, male, female } URL или { narrator: { audio_uri }, ... }.
 * При proxy запрос идёт через /app-api. При ошибке (404/502 и т.д.) ошибка пробрасывается, чтобы UI показал previewError.
 */
export async function getPreviewBySpeakers(
  bookId: string,
  voiceIds: { narrator?: string; male?: string; female?: string },
  speakerSettings?: SpeakerSettings
): Promise<PreviewBySpeakersResponse> {
  if (!isAppApiEnabled()) return {};
  const body: { book_id: string; voice_ids?: Record<string, string>; speaker_settings?: SpeakerSettings } = {
    book_id: bookId,
  };
  if (voiceIds.narrator || voiceIds.male || voiceIds.female) {
    body.voice_ids = {};
    if (voiceIds.narrator) body.voice_ids.narrator = voiceIds.narrator;
    if (voiceIds.male) body.voice_ids.male = voiceIds.male;
    if (voiceIds.female) body.voice_ids.female = voiceIds.female;
  }
  if (speakerSettings && Object.keys(speakerSettings).length > 0) body.speaker_settings = speakerSettings;
  const res = await appJson<Record<string, unknown>>('/internal/preview-by-speakers', {
    method: 'POST',
    body: JSON.stringify(body),
  });
  const base = getPreviewBaseUrl();
  const toFull = (u: string) => (u && !u.startsWith('http') ? base.replace(/\/$/, '') + (u.startsWith('/') ? u : `/${u}`) : u);
  const pickUri = (v: unknown): string | undefined => {
    if (typeof v === 'string') return v;
    if (v && typeof v === 'object' && typeof (v as { audio_uri?: string }).audio_uri === 'string') return (v as { audio_uri: string }).audio_uri;
    return undefined;
  };
  const narratorUri = pickUri(res?.narrator);
  const maleUri = pickUri(res?.male);
  const femaleUri = pickUri(res?.female);
  if (narratorUri || maleUri || femaleUri) {
    return {
      narrator: narratorUri ? toFull(narratorUri) : undefined,
      male: maleUri ? toFull(maleUri) : undefined,
      female: femaleUri ? toFull(femaleUri) : undefined,
    };
  }
  return {};
}
