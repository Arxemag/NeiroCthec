'use client';

import { useState } from 'react';
import { Button } from '../../../components/ui';
import { apiJson } from '../../../lib/api';
import { setAccessToken } from '../../../lib/auth';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

type RegisterResponse = {
  accessToken: string;
};

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await apiJson<RegisterResponse>('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      setAccessToken(data.accessToken);
      router.push('/app/projects');
    } catch (e: any) {
      setError(e?.message ?? 'Ошибка регистрации');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
      <h1 className="text-2xl font-semibold">Регистрация</h1>
      <p className="mt-2 text-sm text-zinc-300">
        Уже есть аккаунт?{' '}
        <Link className="text-indigo-400 hover:text-indigo-300" href="/auth/login">
          Войти
        </Link>
      </p>

      <form className="mt-6 space-y-4" onSubmit={onSubmit}>
        <div>
          <label className="text-sm text-zinc-300">Email</label>
          <input
            className="mt-1 w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 outline-none focus:border-indigo-500"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            required
          />
        </div>
        <div>
          <label className="text-sm text-zinc-300">Пароль (минимум 8 символов)</label>
          <input
            className="mt-1 w-full rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 outline-none focus:border-indigo-500"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            required
            minLength={8}
          />
        </div>

        {error && <div className="rounded-lg border border-red-900 bg-red-950/40 p-3 text-sm text-red-200">{error}</div>}

        <Button disabled={loading} type="submit" className="w-full">
          {loading ? 'Создаём…' : 'Создать аккаунт'}
        </Button>
      </form>
    </div>
  );
}

