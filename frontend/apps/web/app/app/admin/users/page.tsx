'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { apiJson } from '../../../../lib/api';

type User = {
  id: string;
  email: string;
  role: string;
  subscriptionStatus: string;
  createdAt: string;
  _count: { projects: number; audios: number };
  subscription?: { status: string; plan?: { name: string } } | null;
};

const glass = 'rounded-2xl border border-zinc-300/50 bg-zinc-100/90 shadow-xl backdrop-blur-xl';

export default function AdminUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiJson<{ users: User[] }>('/api/admin/users');
        setUsers(data.users);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Ошибка загрузки');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-4">
        <Link href="/app/admin" className="text-sm text-[#7A6CFF] hover:underline">
          ← Админ-панель
        </Link>
        <h1 className="text-2xl font-semibold text-[var(--color-primary)]">Пользователи</h1>
        <Link href="/app/admin/users/raw" className="text-sm text-[#7A6CFF] hover:underline">
          Все значения (ID = *)
        </Link>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>
      )}

      {loading && <div className="text-sm text-zinc-600">Загрузка…</div>}

      {!loading && users.length === 0 && (
        <div className="rounded-xl border border-zinc-300/40 bg-zinc-100/60 py-8 text-center text-sm text-zinc-600">
          Нет пользователей.
        </div>
      )}

      {!loading && users.length > 0 && (
        <div className={`overflow-hidden ${glass}`}>
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-zinc-300/50 bg-zinc-100/70">
                <th className="px-4 py-3 font-medium text-zinc-700">Email</th>
                <th className="px-4 py-3 font-medium text-zinc-700">Роль</th>
                <th className="px-4 py-3 font-medium text-zinc-700">Подписка</th>
                <th className="px-4 py-3 font-medium text-zinc-700">Проекты</th>
                <th className="px-4 py-3 font-medium text-zinc-700">Аудио</th>
                <th className="px-4 py-3 font-medium text-zinc-700">Создан</th>
                <th className="w-32 px-4 py-3" aria-label="Действия" />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-b border-zinc-200/60 last:border-b-0 hover:bg-zinc-50/80">
                  <td className="px-4 py-3 font-medium text-zinc-900">{u.email}</td>
                  <td className="px-4 py-3 text-zinc-600">{u.role}</td>
                  <td className="px-4 py-3 text-zinc-600">{u.subscriptionStatus}</td>
                  <td className="px-4 py-3 text-zinc-600">{u._count.projects}</td>
                  <td className="px-4 py-3 text-zinc-600">{u._count.audios}</td>
                  <td className="px-4 py-3 text-zinc-500">
                    {new Date(u.createdAt).toLocaleDateString('ru-RU')}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      href={`/app/admin/users/${u.id}`}
                      className="text-[#7A6CFF] hover:underline"
                    >
                      Подробнее
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
