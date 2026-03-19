export type Session = {
  accessToken: string;
};

const KEY = 'neurochtec_access_token';
const USER_ID_KEY = 'neurochtec_user_id';
/** Имя cookie для проверки в middleware: личный кабинет только для авторизованных */
export const AUTH_COOKIE_NAME = 'neurochtec_signed_in';

export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(KEY);
}

export function setAccessToken(token: string) {
  window.localStorage.setItem(KEY, token);
  if (typeof document !== 'undefined') {
    document.cookie = `${AUTH_COOKIE_NAME}=1; path=/; max-age=604800; SameSite=Lax`;
  }
}

export function clearAccessToken() {
  window.localStorage.removeItem(KEY);
  if (typeof window !== 'undefined') window.localStorage.removeItem(USER_ID_KEY);
  if (typeof document !== 'undefined') {
    document.cookie = `${AUTH_COOKIE_NAME}=; path=/; max-age=0`;
  }
}

/** Идентификатор пользователя для заголовка X-User-Id при вызовах app API (не зависит от app). */
export function getStoredUserId(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem(USER_ID_KEY);
}

export function setStoredUserId(userId: string) {
  window.localStorage.setItem(USER_ID_KEY, userId);
}

