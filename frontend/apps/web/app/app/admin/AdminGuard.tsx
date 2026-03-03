'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { useUser } from '../../../lib/use-user';

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, isLoading, isAdmin } = useUser();

  useEffect(() => {
    if (!isLoading) {
      if (!user) {
        // Пользователь не авторизован
        router.replace('/auth/login');
      } else if (!isAdmin) {
        // Пользователь не админ - редирект на проекты
        router.replace('/app/projects');
      }
    }
  }, [user, isLoading, isAdmin, router]);

  // Показываем загрузку пока проверяем права
  if (isLoading) {
    return <div className="p-6 text-sm text-zinc-600">Проверка доступа…</div>;
  }

  // Если пользователь не админ, ничего не показываем (редирект уже произошел)
  if (!isAdmin) {
    return null;
  }

  return <>{children}</>;
}
