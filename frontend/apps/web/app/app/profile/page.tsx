'use client';

import { useEffect, useState } from 'react';
import { apiJson } from '../../../lib/api';

type Me = { user: { id: string; email: string; role: string; subscriptionStatus: string; createdAt: string } };

export default function ProfilePage() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [promoteLoading, setPromoteLoading] = useState(false);
  const [promoteError, setPromoteError] = useState<string | null>(null);
  const [promoteSuccess, setPromoteSuccess] = useState(false);

  const isDevEnv = process.env.NODE_ENV !== 'production';

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

  const handleBecomeAdmin = async () => {
    setPromoteLoading(true);
    setPromoteError(null);
    setPromoteSuccess(false);
    try {
      const data = await apiJson<Me>('/api/users/me/dev-become-admin', { method: 'POST' });
      setMe(data);
      setPromoteSuccess(true);
    } catch (e: any) {
      setPromoteError(e?.message ?? 'Не удалось выдать роль администратора');
    } finally {
      setPromoteLoading(false);
    }
  };

  return (
    <div>
      <h1 className="font-heading text-2xl font-semibold text-text">Профиль</h1>
      <p className="mt-1 text-sm text-textSecondary">Базовая информация аккаунта (MVP).</p>

      {error && <div className="mt-4 rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>}

      <div className="mt-6 rounded-2xl border border-zinc-300/40 bg-zinc-100/80 p-4">
        {me ? (
          <div className="space-y-4 text-sm text-zinc-700">
            <div className="space-y-2">
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

            {isDevEnv && me.user.role !== 'admin' && (
              <div className="space-y-2 border-t border-dashed border-zinc-300 pt-3">
                <div className="text-xs text-zinc-500">
                  Временная dev-кнопка: выдаёт текущему пользователю роль администратора. В проде будет удалена.
                </div>
                {promoteError && (
                  <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
                    {promoteError}
                  </div>
                )}
                {promoteSuccess && (
                  <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
                    Роль администратора выдана. При необходимости перелогиньтесь, чтобы обновить доступы.
                  </div>
                )}
                <button
                  type="button"
                  onClick={handleBecomeAdmin}
                  disabled={promoteLoading}
                  className="inline-flex items-center rounded-lg bg-zinc-900 px-4 py-2 text-xs font-medium text-zinc-50 hover:bg-zinc-800 disabled:opacity-50"
                >
                  {promoteLoading ? 'Выдаю роль…' : 'Сделать себя админом (dev)'}
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-zinc-600">Загрузка…</div>
        )}
      </div>
    </div>
  );
}

