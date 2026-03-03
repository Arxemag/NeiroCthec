import { useEffect, useState } from 'react';
import { apiJson } from './api';
import { getAccessToken, getStoredUserId } from './auth';

export type User = {
  id: string;
  email: string;
  role: 'user' | 'admin';
};

type MeResponse = {
  user: User;
};

/** Пользователь по умолчанию, когда бэкенд не отдаёт /api/users/me (например, только app API без сервиса авторизации). */
function fallbackUser(): User {
  const id = getStoredUserId() ?? 'dev-user';
  return { id, email: id, role: 'user' };
}

/**
 * Хук для получения информации о текущем пользователе
 */
export function useUser() {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;

    const token = getAccessToken();
    if (!token) {
      setIsLoading(false);
      setUser(null);
      setError(new Error('No token'));
      return;
    }

    (async () => {
      try {
        const data = await apiJson<MeResponse>('/api/users/me');
        if (!cancelled) {
          setUser(data?.user || null);
          setError(null);
        }
      } catch (e: any) {
        if (!cancelled) {
          const msg = e?.message ?? String(e);
          if (msg.includes('404') || msg.includes('Not Found')) {
            setUser(fallbackUser());
            setError(null);
          } else {
            setUser(null);
            setError(e);
          }
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  return { user, isLoading, error, isAdmin: user?.role === 'admin' };
}
