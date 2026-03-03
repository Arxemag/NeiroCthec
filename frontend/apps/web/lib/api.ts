import { getAccessToken, setAccessToken, clearAccessToken, getStoredUserId } from './auth';

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:4000';

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

