'use client';

import { useEffect, useState } from 'react';
import { apiJson } from '../../../lib/api';

type Me = { user: { id: string; email: string; role: string; subscriptionStatus: string; createdAt: string } };

export default function ProfilePage() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await apiJson<Me>('/api/users/me');
        setMe(data);
      } catch (e: any) {
        setError(e?.message ?? 'Ошибка');
      }
    })();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold">Профиль</h1>
      <p className="mt-1 text-sm text-zinc-600">Базовая информация аккаунта (MVP).</p>

      {error && <div className="mt-4 rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>}

      <div className="mt-6 rounded-2xl border border-zinc-300/40 bg-zinc-100/80 p-4">
        {me ? (
          <div className="space-y-2 text-sm text-zinc-700">
            <div>
              Email: <span className="text-zinc-900">{me.user.email}</span>
            </div>
            <div>
              Role: <span className="text-zinc-900">{me.user.role}</span>
            </div>
            <div>
              Subscription: <span className="text-zinc-900">{me.user.subscriptionStatus}</span>
            </div>
            <div className="text-xs text-zinc-500">Created: {new Date(me.user.createdAt).toLocaleString()}</div>
          </div>
        ) : (
          <div className="text-sm text-zinc-600">Загрузка…</div>
        )}
      </div>
    </div>
  );
}

