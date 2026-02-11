import { getAccessToken, clearAccessToken } from './auth';

const RAW_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() ?? '';
// For browser calls inside Next app we prefer same-origin `/api/*` endpoints.
// When RAW_API_BASE is provided and absolute, keep it for non-browser usage.
export const API_BASE = typeof window === 'undefined' ? RAW_API_BASE : '';

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(init.headers ?? {});

  if (!headers.has('Content-Type') && init.body && typeof init.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: 'include',
    cache: 'no-store',
  });

  if (response.status === 401) {
    clearAccessToken();
  }

  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const errorData = (await response.json()) as { message?: string | string[] };
      if (Array.isArray(errorData.message)) message = errorData.message.join(', ');
      else if (typeof errorData.message === 'string') message = errorData.message;
    } catch {
      // fallback to HTTP status text only
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return (await response.json()) as T;
}
