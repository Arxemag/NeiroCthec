'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { apiJson } from '../../../lib/api';

type Metrics = {
  totalUsers: number;
  totalProjects: number;
  totalAudios: number;
  projectsByStatus: Record<string, number>;
  audiosByStatus: Record<string, number>;
  subscriptionByStatus: Record<string, number>;
  newUsersLast7Days: number;
  newUsersLast30Days: number;
  projectsCreatedLast7Days: number;
  audiosCreatedLast7Days: number;
};

const glass = 'rounded-2xl border border-zinc-300/50 bg-zinc-100/90 shadow-xl backdrop-blur-xl';
const glassCard = 'rounded-2xl border border-zinc-300/40 bg-zinc-100/80 backdrop-blur-lg';

export default function AdminPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiJson<Metrics>('/api/admin/metrics');
        setMetrics(data);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Ошибка загрузки');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-text">Админ-панель</h1>
          <p className="mt-1 text-sm text-textSecondary">Метрики и управление пользователями</p>
        </div>
        <Link
          href="/app/admin/users"
          className="inline-flex items-center rounded-lg bg-zinc-800 px-4 py-2 font-medium text-zinc-50 hover:bg-zinc-700"
        >
          Пользователи
        </Link>
        <Link
          href="/app/admin/voices"
          className="inline-flex items-center rounded-lg bg-zinc-800 px-4 py-2 font-medium text-zinc-50 hover:bg-zinc-700"
        >
          Голоса
        </Link>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>
      )}

      {loading && <div className="text-sm text-zinc-600">Загрузка метрик…</div>}

      {metrics && !loading && (
        <div className={`${glass} p-6`}>
          <h2 className="text-lg font-semibold text-zinc-800">Метрики сервиса</h2>

          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className={`${glassCard} p-4`}>
              <div className="text-2xl font-bold text-[#7A6CFF]">{metrics.totalUsers}</div>
              <div className="text-sm text-zinc-600">Пользователей</div>
            </div>
            <div className={`${glassCard} p-4`}>
              <div className="text-2xl font-bold text-[#7A6CFF]">{metrics.totalProjects}</div>
              <div className="text-sm text-zinc-600">Проектов</div>
            </div>
            <div className={`${glassCard} p-4`}>
              <div className="text-2xl font-bold text-[#7A6CFF]">{metrics.totalAudios}</div>
              <div className="text-sm text-zinc-600">Аудио</div>
            </div>
            <div className={`${glassCard} p-4`}>
              <div className="text-2xl font-bold text-emerald-600">+{metrics.newUsersLast7Days}</div>
              <div className="text-sm text-zinc-600">Новых за 7 дней</div>
            </div>
          </div>

          <div className="mt-6 grid gap-6 md:grid-cols-2">
            <div className={`${glassCard} p-4`}>
              <h3 className="font-medium text-zinc-800">Проекты по статусу</h3>
              <ul className="mt-2 space-y-1 text-sm text-zinc-600">
                {Object.entries(metrics.projectsByStatus).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v}
                  </li>
                ))}
              </ul>
            </div>
            <div className={`${glassCard} p-4`}>
              <h3 className="font-medium text-zinc-800">Аудио по статусу</h3>
              <ul className="mt-2 space-y-1 text-sm text-zinc-600">
                {Object.entries(metrics.audiosByStatus).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-4">
            <div className={`${glassCard} p-4`}>
              <h3 className="font-medium text-zinc-800">Подписки по статусу</h3>
              <ul className="mt-2 space-y-1 text-sm text-zinc-600">
                {Object.entries(metrics.subscriptionByStatus).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="text-sm text-zinc-600">
              Новых пользователей за 30 дней: <strong className="text-zinc-800">{metrics.newUsersLast30Days}</strong>
            </div>
            <div className="text-sm text-zinc-600">
              Проектов создано за 7 дней: <strong className="text-zinc-800">{metrics.projectsCreatedLast7Days}</strong>
            </div>
            <div className="text-sm text-zinc-600">
              Аудио создано за 7 дней: <strong className="text-zinc-800">{metrics.audiosCreatedLast7Days}</strong>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
