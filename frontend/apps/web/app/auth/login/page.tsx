'use client';

import { useState } from 'react';
import { Button } from '../../../components/ui';
import { Card } from '../../../components/ui/card';
import { setAccessToken, setStoredUserId } from '../../../lib/auth';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:4000';

type LoginResponse = { accessToken: string };

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextUrl = searchParams.get('next');
  const redirectTo = nextUrl && nextUrl.startsWith('/app') ? nextUrl : '/app/projects';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });
      if (res.ok) {
        const data = (await res.json()) as LoginResponse;
        setAccessToken(data.accessToken);
        setStoredUserId(email ?? '');
        router.push(redirectTo);
        return;
      }
      const text = await res.text();
      let msg = text;
      try {
        const j = JSON.parse(text);
        if (typeof (j as any)?.message === 'string') msg = (j as any).message;
        else if (typeof (j as any)?.detail === 'string') msg = (j as any).detail;
      } catch {}
      setError(msg || 'Ошибка входа');
    } catch (_e: any) {
      setError('Не удалось подключиться к серверу. Проверьте сеть и повторите.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="mx-auto max-w-md p-6">
      <h1 className="font-heading text-2xl font-semibold text-text">Вход</h1>
      <p className="mt-2 text-sm text-textSecondary">
        Нет аккаунта?{' '}
        <Link className="text-accent hover:underline transition-colors" href="/auth/register">
          Зарегистрироваться
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
          <div className="flex items-center justify-between">
            <label className="text-sm text-text">Пароль</label>
            <Link className="text-xs text-accent hover:underline transition-colors" href="/auth/forgot-password">
              Забыли пароль?
            </Link>
          </div>
          <input
            className="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-text outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-colors"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            required
          />
        </div>

        {error && (
          <div className="rounded-lg border border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
            {error}
          </div>
        )}

        <Button disabled={loading} type="submit" variant="primary" className="w-full">
          {loading ? 'Входим…' : 'Войти'}
        </Button>
      </form>
    </Card>
  );
}

