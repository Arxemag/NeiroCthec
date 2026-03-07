import { useEffect, useState } from 'react';
import { apiJson } from './api';
import { getAccessToken } from './auth';

export type User = {
  id: string;
  email: string;
  role: 'user' | 'admin';
};

type MeResponse = {
  user: User;
};

/**
 * Хук для получения информации о текущем пользователе.
 * Анонимных пользователей нет: при отсутствии токена или ошибке API (в т.ч. 404/401) возвращает user=null.
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
          setUser(null);
          setError(e instanceof Error ? e : new Error(String(e)));
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
