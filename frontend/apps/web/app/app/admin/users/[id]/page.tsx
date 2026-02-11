'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { apiJson } from '../../../../../lib/api';
import { Button } from '../../../../../components/ui';

type Project = {
  id: string;
  title: string;
  status: string;
  language: string;
  createdAt: string;
  _count: { audios: number };
};

type UserDetail = {
  id: string;
  email: string;
  role: string;
  subscriptionStatus: string;
  createdAt: string;
  updatedAt: string;
  projects: Project[];
  _count: { audios: number };
  subscription?: { status: string; plan?: { name: string } } | null;
};

const glassCard = 'rounded-2xl border border-zinc-300/40 bg-zinc-100/80 backdrop-blur-lg';

export default function AdminUserDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [user, setUser] = useState<UserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changing, setChanging] = useState(false);
  const [changeError, setChangeError] = useState<string | null>(null);
  const [changeSuccess, setChangeSuccess] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiJson<{ user: UserDetail }>(`/api/admin/users/${id}`);
      setUser(data.user);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword.length < 8) {
      setChangeError('Пароль не менее 8 символов');
      return;
    }
    if (newPassword !== confirmPassword) {
      setChangeError('Пароли не совпадают');
      return;
    }
    setChanging(true);
    setChangeError(null);
    setChangeSuccess(false);
    try {
      await apiJson(`/api/admin/users/${id}/password`, {
        method: 'PATCH',
        body: JSON.stringify({ newPassword }),
      });
      setNewPassword('');
      setConfirmPassword('');
      setChangeSuccess(true);
    } catch (e: unknown) {
      setChangeError(e instanceof Error ? e.message : 'Не удалось изменить пароль');
    } finally {
      setChanging(false);
    }
  }

  if (loading) return <div className="text-sm text-zinc-600">Загрузка…</div>;
  if (!user) return <div className="text-sm text-zinc-600">Пользователь не найден</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/app/admin/users" className="text-sm text-[#7A6CFF] hover:underline">
          ← Пользователи
        </Link>
        <h1 className="text-2xl font-semibold text-[var(--color-primary)]">{user.email}</h1>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>
      )}

      <div className={`${glassCard} p-6`}>
        <h2 className="font-medium text-zinc-800">Данные пользователя</h2>
        <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
          <dt className="text-zinc-500">Роль</dt>
          <dd className="text-zinc-800">{user.role}</dd>
          <dt className="text-zinc-500">Подписка</dt>
          <dd className="text-zinc-800">{user.subscriptionStatus}</dd>
          <dt className="text-zinc-500">Создан</dt>
          <dd className="text-zinc-800">{new Date(user.createdAt).toLocaleString('ru-RU')}</dd>
          <dt className="text-zinc-500">Обновлён</dt>
          <dd className="text-zinc-800">{new Date(user.updatedAt).toLocaleString('ru-RU')}</dd>
          <dt className="text-zinc-500">Всего аудио</dt>
          <dd className="text-zinc-800">{user._count.audios}</dd>
        </dl>
      </div>

      <div className={`${glassCard} p-6`}>
        <h2 className="font-medium text-zinc-800">Сбросить пароль</h2>
        <p className="mt-1 text-sm text-zinc-600">Установите новый пароль для входа пользователя.</p>
        <form className="mt-4 max-w-sm space-y-3" onSubmit={handleChangePassword}>
          <div>
            <label className="block text-sm text-zinc-700">Новый пароль</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-zinc-300/40 bg-zinc-100/80 px-3 py-2 text-zinc-900 outline-none focus:border-[#7A6CFF]"
              placeholder="минимум 8 символов"
              minLength={8}
            />
          </div>
          <div>
            <label className="block text-sm text-zinc-700">Подтверждение</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-zinc-300/40 bg-zinc-100/80 px-3 py-2 text-zinc-900 outline-none focus:border-[#7A6CFF]"
              placeholder="повторите пароль"
            />
          </div>
          {changeError && <div className="text-sm text-red-600">{changeError}</div>}
          {changeSuccess && <div className="text-sm text-emerald-600">Пароль успешно изменён</div>}
          <Button type="submit" disabled={changing} variant="secondary">
            {changing ? 'Сохранение…' : 'Сохранить новый пароль'}
          </Button>
        </form>
      </div>

      <div className={`${glassCard} p-6`}>
        <h2 className="font-medium text-zinc-800">Проекты ({user.projects.length})</h2>
        {user.projects.length === 0 ? (
          <p className="mt-2 text-sm text-zinc-500">Нет проектов</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-300/50 text-left">
                  <th className="pb-2 font-medium text-zinc-600">Название</th>
                  <th className="pb-2 font-medium text-zinc-600">Статус</th>
                  <th className="pb-2 font-medium text-zinc-600">Язык</th>
                  <th className="pb-2 font-medium text-zinc-600">Аудио</th>
                  <th className="pb-2 font-medium text-zinc-600">Создан</th>
                </tr>
              </thead>
              <tbody>
                {user.projects.map((p) => (
                  <tr key={p.id} className="border-b border-zinc-200/60">
                    <td className="py-2 text-zinc-800">{p.title}</td>
                    <td className="py-2 text-zinc-600">{p.status}</td>
                    <td className="py-2 text-zinc-600">{p.language}</td>
                    <td className="py-2 text-zinc-600">{p._count.audios}</td>
                    <td className="py-2 text-zinc-500">{new Date(p.createdAt).toLocaleDateString('ru-RU')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
