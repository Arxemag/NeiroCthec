'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { apiJson } from '../../../lib/api';

type Me = { user: { id: string; email: string; role: string } };

export function AdminGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ok, setOk] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await apiJson<Me>('/api/users/me');
        if (!cancelled && data?.user?.role !== 'admin') router.replace('/app/projects');
        else if (!cancelled) setOk(true);
      } catch {
        if (!cancelled) router.replace('/auth/login');
      }
    })();
    return () => { cancelled = true; };
  }, [router]);

  if (ok !== true) return <div className="p-6 text-sm text-zinc-600">Проверка доступа…</div>;
  return <>{children}</>;
}
