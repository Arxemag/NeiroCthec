'use client';

import { useState } from 'react';
import { Button } from '../../../components/ui';
import { apiJson } from '../../../lib/api';
import { setAccessToken } from '../../../lib/auth';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

type LoginResponse = {
  accessToken: string;
};

export default function LoginPage() {
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
      const data = await apiJson<LoginResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      setAccessToken(data.accessToken);
      router.push('/app/projects');
    } catch (e: any) {
      setError(e?.message ?? 'Ошибка входа');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-zinc-300/50 bg-zinc-100/90 p-6 shadow-xl backdrop-blur-xl">
      <h1 className="text-2xl font-semibold text-[var(--color-primary)]">Вход</h1>
      <p className="mt-2 text-sm text-zinc-600">
        Нет аккаунта?{' '}
        <Link className="text-[#7A6CFF] hover:underline" href="/auth/register">
          Зарегистрироваться
        </Link>
      </p>

      <form className="mt-6 space-y-4" onSubmit={onSubmit}>
        <div>
          <label className="text-sm text-zinc-700">Email</label>
          <input
            className="mt-1 w-full rounded-lg border border-zinc-300/40 bg-zinc-100/80 px-3 py-2 text-zinc-900 outline-none focus:border-[#7A6CFF]"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            required
          />
        </div>
        <div>
          <div className="flex items-center justify-between">
            <label className="text-sm text-zinc-700">Пароль</label>
            <Link className="text-xs text-[#7A6CFF] hover:underline" href="/auth/forgot-password">
              Забыли пароль?
            </Link>
          </div>
          <input
            className="mt-1 w-full rounded-lg border border-zinc-300/40 bg-zinc-100/80 px-3 py-2 text-zinc-900 outline-none focus:border-[#7A6CFF]"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            required
          />
        </div>

        {error && <div className="rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>}

        <Button disabled={loading} type="submit" className="w-full !bg-[var(--color-accent)] !text-[var(--color-primary)]">
          {loading ? 'Входим…' : 'Войти'}
        </Button>
      </form>
    </div>
  );
}

