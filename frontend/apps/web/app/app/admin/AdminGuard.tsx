'use client';

import { useRouter, usePathname } from 'next/navigation';
import { useEffect } from 'react';
import { useUser } from '../../../lib/use-user';

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isLoading, isAdmin } = useUser();
  const isPublicAdminVoices = pathname?.startsWith('/app/admin/voices');

  useEffect(() => {
    if (!isLoading) {
      if (!user) {
        // Пользователь не авторизован
        router.replace('/auth/login');
      } else if (!isAdmin && !isPublicAdminVoices) {
        // Пользователь не админ - редирект на проекты
        router.replace('/app/projects');
      }
    }
  }, [user, isLoading, isAdmin, isPublicAdminVoices, router]);

  // Показываем загрузку пока проверяем права
  if (isLoading) {
    return <div className="p-6 text-sm text-zinc-600">Проверка доступа…</div>;
  }

  // Если пользователь не админ, ничего не показываем (редирект уже произошел)
  if (!isAdmin && !isPublicAdminVoices) {
    return null;
  }

  return <>{children}</>;
}
