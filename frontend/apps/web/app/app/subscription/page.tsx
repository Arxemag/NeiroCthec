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
      <h1 className="font-heading text-2xl font-semibold text-text">Подписка</h1>
      <p className="mt-1 text-sm text-textSecondary">В MVP — заглушка: кнопка «апгрейд» просто переключает статус.</p>

      {error && <div className="mt-4 rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>}

      <div className="mt-6 rounded-2xl border border-zinc-300/40 bg-zinc-100/80 p-4">
        {loading ? (
          <div className="text-sm text-zinc-600">Загрузка…</div>
        ) : sub ? (
          <div className="space-y-2 text-sm text-zinc-700">
            <div>
              Статус: <span className="text-zinc-900">{sub.status}</span>
            </div>
            <div>
              План: <span className="text-zinc-900">{sub.plan?.name ?? '—'}</span>
            </div>
            <div className="text-zinc-600">
              Download: {sub.plan?.canDownload ? 'включён' : 'выключен'} (в UI не показываем кнопку скачивания)
            </div>
          </div>
        ) : (
          <div className="text-sm text-zinc-600">Нет данных подписки</div>
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

