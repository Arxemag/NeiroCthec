import { getAccessToken, setAccessToken, clearAccessToken } from './auth';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:4000';

async function apiFetch(path: string, init: RequestInit = {}) {
  const token = getAccessToken();
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);

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
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const message = data?.message ?? data?.error ?? `HTTP ${res.status}`;
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
  }
  return data as T;
}

