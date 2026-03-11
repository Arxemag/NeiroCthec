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
        router.replace('/auth/login');
      } else if (!isAdmin) {
        router.replace('/app/projects');
      }
    }
  }, [user, isLoading, isAdmin, router]);

  if (isLoading) {
    return <div className="p-6 text-sm text-zinc-600">Проверка доступа…</div>;
  }

  if (!isAdmin) {
    return null;
  }

  return <>{children}</>;
}
