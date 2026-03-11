'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

/** Редирект: функционал голосов перенесён на главную страницу админ-панели. */
export default function AdminVoicesRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/app/admin');
  }, [router]);
  return <div className="p-6 text-sm text-zinc-600">Перенаправление в админ-панель…</div>;
}
