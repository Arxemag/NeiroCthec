export type Session = {
  accessToken: string;
};

const KEY = 'neurochtec_access_token';
const USER_ID_KEY = 'neurochtec_user_id';

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(KEY);
}

export function setAccessToken(token: string) {
  window.localStorage.setItem(KEY, token);
}

export function clearAccessToken() {
  window.localStorage.removeItem(KEY);
  if (typeof window !== 'undefined') window.localStorage.removeItem(USER_ID_KEY);
}

/** Идентификатор пользователя для заголовка X-User-Id при вызовах app API (не зависит от app). */
export function getStoredUserId(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(USER_ID_KEY);
}

export function setStoredUserId(userId: string) {
  window.localStorage.setItem(USER_ID_KEY, userId);
}

