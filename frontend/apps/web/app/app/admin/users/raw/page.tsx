'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { apiJson } from '../../../../../lib/api';

type User = {
  id: string;
  email: string;
  role: string;
  subscriptionStatus: string;
  createdAt: string;
  _count: { projects: number; audios: number };
  subscription?: { status: string; plan?: { name: string } } | null;
};

export default function AdminUsersRawPage() {
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

  const maskedUsers = useMemo(() => users.map((u) => ({ ...u, id: '*' })), [users]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/app/admin/users" className="text-sm text-[#7A6CFF] hover:underline">
          ← Пользователи
        </Link>
        <h1 className="text-2xl font-semibold text-[var(--color-primary)]">Все значения пользователей</h1>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>}
      {loading && <div className="text-sm text-zinc-600">Загрузка…</div>}

      {!loading && !error && (
        <div className="rounded-2xl border border-zinc-300/40 bg-zinc-100/80 p-4">
          <p className="mb-3 text-sm text-zinc-600">`id` пользователей замаскированы символом `*`.</p>
          <pre className="overflow-x-auto rounded-lg bg-zinc-900 p-4 text-xs text-zinc-100">
            {JSON.stringify(maskedUsers, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
