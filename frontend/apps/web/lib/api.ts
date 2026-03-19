import { getAccessToken, setAccessToken, clearAccessToken, getStoredUserId } from './auth';

// Пустая строка = запросы на тот же хост (Next проксирует /api/* на Nest). В Docker задаём NEXT_PUBLIC_API_BASE_URL=.
export const API_BASE =
  (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_API_BASE_URL != null)
    ? String(process.env.NEXT_PUBLIC_API_BASE_URL)
    : 'http://localhost:4000';

async function apiFetch(path: string, init: RequestInit = {}) {
  const token = getAccessToken();
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const userId = getStoredUserId() ?? (typeof process.env.NEXT_PUBLIC_DEV_USER_ID === 'string' ? process.env.NEXT_PUBLIC_DEV_USER_ID : null);
  if (userId) headers.set('X-User-Id', userId);

  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: 'include', // for refresh cookie
  });

  if (res.status === 401 && token) {
    // Try refresh once
    const refreshed = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    });
    if (refreshed.ok) {
      const data = await refreshed.json();
      if (data?.accessToken) setAccessToken(data.accessToken);
      return apiFetch(path, init);
    }
    clearAccessToken();
  }

  return res;
}

export async function apiJson<T>(path: string, init: RequestInit = {}) {
  const res = await apiFetch(path, init);
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
      (typeof obj.message === 'string' ? obj.message : null) ??
      (typeof obj.error === 'string' ? obj.error : null) ??
      (text || `HTTP ${res.status}`);
    throw new Error(message);
  }
  return data as T;
}

/** GET /api/users/me/voices — список своих голосов (Nest). Для объединения с встроенными используйте listVoices из app-api. */
export async function listUserVoices(): Promise<{ voices: Array<{ id: string; name: string; role?: string; gender?: string }> }> {
  return apiJson<{ voices: Array<{ id: string; name: string; role?: string; gender?: string }> }>('/api/users/me/voices');
}

/** POST /api/users/me/voices — загрузить свой голос (WAV). Multipart: file, опционально name, role. */
export async function uploadUserVoice(
  file: File,
  options?: { name?: string; role?: 'narrator' | 'male' | 'female' }
): Promise<{ id: string; name?: string; role?: string }> {
  const token = getAccessToken();
  const headers = new Headers();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const userId = getStoredUserId() ?? (typeof process.env.NEXT_PUBLIC_DEV_USER_ID === 'string' ? process.env.NEXT_PUBLIC_DEV_USER_ID : null);
  if (userId) headers.set('X-User-Id', userId);
  const formData = new FormData();
  formData.append('file', file);
  if (options?.name?.trim()) formData.append('name', options.name.trim());
  if (options?.role) formData.append('role', options.role);
  const res = await fetch(`${API_BASE}/api/users/me/voices`, {
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
    const message =
      (typeof obj.message === 'string' ? obj.message : null) ??
      (typeof obj.error === 'string' ? obj.error : null) ??
      (text || `HTTP ${res.status}`);
    throw new Error(message);
  }
  const out = data as { id: string; name?: string; role?: string };
  return { id: out.id, name: out.name, role: out.role };
}

/** DELETE /api/users/me/voices/:id — удалить свой голос (Nest). */
export async function deleteUserVoice(voiceId: string): Promise<void> {
  await apiJson<unknown>(`/api/users/me/voices/${encodeURIComponent(voiceId)}`, { method: 'DELETE' });
}

