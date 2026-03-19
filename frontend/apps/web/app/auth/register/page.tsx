'use client';

import { useState } from 'react';
import { Button } from '../../../components/ui';
import { Card } from '../../../components/ui/card';
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
    <Card className="mx-auto max-w-md p-6">
      <h1 className="font-heading text-2xl font-semibold text-text">Регистрация</h1>
      <p className="mt-2 text-sm text-textSecondary">
        Уже есть аккаунт?{' '}
        <Link className="text-accent hover:underline transition-colors" href="/auth/login">
          Войти
        </Link>
      </p>

      <form className="mt-6 space-y-4" onSubmit={onSubmit}>
        <div>
          <label className="text-sm text-text">Email</label>
          <input
            className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-text outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-colors"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            required
          />
        </div>
        <div>
          <label className="text-sm text-text">Пароль (минимум 8 символов)</label>
          <input
            className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-text outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-colors"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            required
            minLength={8}
          />
        </div>

        <Button disabled={loading} type="submit" variant="primary" className="w-full">
          {loading ? 'Создаём…' : 'Создать аккаунт'}
        </Button>
      </form>

      {error && (
        <div className="mt-4 rounded-lg border border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      {showLoginForm && (
        <div className="mt-6 border-t border-border pt-6">
          <p className="text-sm font-medium text-text">Войти в существующий аккаунт</p>
          <form className="mt-4 space-y-4" onSubmit={onLoginSubmit}>
            <div>
              <label className="text-sm text-text">Email</label>
              <input
                className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-text outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-colors"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                type="email"
                required
              />
            </div>
            <div>
              <label className="text-sm text-text">Пароль</label>
              <input
                className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-text outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-colors"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                type="password"
                required
              />
            </div>
            <Button disabled={loading} type="submit" variant="primary" className="w-full">
              {loading ? 'Входим…' : 'Войти'}
            </Button>
          </form>
        </div>
      )}
    </Card>
  );
}

