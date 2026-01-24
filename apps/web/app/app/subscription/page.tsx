'use client';

import { useEffect, useState } from 'react';
import { apiJson } from '../../../lib/api';
import { Button } from '../../../components/ui';

type Subscription = {
  status: string;
  plan: null | { name: string; monthlyPriceCents: number; maxCharactersMonth: number; canDownload: boolean };
};

export default function SubscriptionPage() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiJson<{ subscription: Subscription | null }>('/api/subscription');
      setSub(data.subscription);
    } catch (e: any) {
      setError(e?.message ?? 'Ошибка');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function upgrade() {
    setUpgrading(true);
    setError(null);
    try {
      const data = await apiJson<{ subscription: Subscription | null }>('/api/subscription/upgrade', { method: 'POST' });
      setSub(data.subscription);
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось обновить');
    } finally {
      setUpgrading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-semibold">Подписка</h1>
      <p className="mt-1 text-sm text-zinc-300">В MVP — заглушка: кнопка «апгрейд» просто переключает статус.</p>

      {error && <div className="mt-4 rounded-lg border border-red-900 bg-red-950/40 p-3 text-sm text-red-200">{error}</div>}

      <div className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-950/40 p-4">
        {loading ? (
          <div className="text-sm text-zinc-300">Загрузка…</div>
        ) : sub ? (
          <div className="space-y-2 text-sm">
            <div>
              Статус: <span className="text-zinc-100">{sub.status}</span>
            </div>
            <div>
              План: <span className="text-zinc-100">{sub.plan?.name ?? '—'}</span>
            </div>
            <div className="text-zinc-400">
              Download: {sub.plan?.canDownload ? 'включён' : 'выключен'} (в UI не показываем кнопку скачивания)
            </div>
          </div>
        ) : (
          <div className="text-sm text-zinc-300">Нет данных подписки</div>
        )}

        <div className="mt-4 flex gap-2">
          <Button disabled={upgrading} onClick={upgrade}>
            {upgrading ? 'Обновляем…' : 'Обновить план (stub)'}
          </Button>
          <Button variant="secondary" onClick={load}>
            Обновить
          </Button>
        </div>
      </div>
    </div>
  );
}

