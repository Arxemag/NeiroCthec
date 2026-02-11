'use client';

import { useState } from 'react';
import { Button } from '../../../components/ui';
import { apiJson } from '../../../lib/api';
import { setAccessToken } from '../../../lib/auth';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

type RegisterResponse = { accessToken: string };
type LoginResponse = { accessToken: string };

const isAlreadyRegistered = (msg: unknown) =>
  typeof msg === 'string' && /already registered|уже зарегистрирован/i.test(msg);

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showLoginForm, setShowLoginForm] = useState(false);

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
      const msg = e?.message ?? 'Ошибка регистрации';
      setError(msg);
      if (isAlreadyRegistered(msg)) {
        setShowLoginForm(true);
        setLoginPassword(password);
      }
    } finally {
      setLoading(false);
    }
  }

  async function onLoginSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await apiJson<LoginResponse>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password: loginPassword }),
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
      <h1 className="text-2xl font-semibold text-zinc-900">Регистрация</h1>
      <p className="mt-2 text-sm text-zinc-600">
        Уже есть аккаунт?{' '}
        <Link className="text-[#7A6CFF] hover:underline" href="/auth/login">
          Войти
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
          <label className="text-sm text-zinc-700">Пароль (минимум 8 символов)</label>
          <input
            className="mt-1 w-full rounded-lg border border-zinc-300/40 bg-zinc-100/80 px-3 py-2 text-zinc-900 outline-none focus:border-[#7A6CFF]"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            required
            minLength={8}
          />
        </div>

        <Button disabled={loading} type="submit" className="w-full">
          {loading ? 'Создаём…' : 'Создать аккаунт'}
        </Button>
      </form>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>
      )}

      {showLoginForm && (
        <div className="mt-6 border-t border-zinc-300/50 pt-6">
          <p className="text-sm font-medium text-zinc-700">Войти в существующий аккаунт</p>
          <form className="mt-4 space-y-4" onSubmit={onLoginSubmit}>
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
              <label className="text-sm text-zinc-700">Пароль</label>
              <input
                className="mt-1 w-full rounded-lg border border-zinc-300/40 bg-zinc-100/80 px-3 py-2 text-zinc-900 outline-none focus:border-[#7A6CFF]"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                type="password"
                required
              />
            </div>
            <Button
              disabled={loading}
              type="submit"
              className="w-full !bg-[var(--color-accent)] !text-[var(--color-primary)]"
            >
              {loading ? 'Входим…' : 'Войти'}
            </Button>
          </form>
        </div>
      )}
    </div>
  );
}

