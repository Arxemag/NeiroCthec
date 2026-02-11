'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { getAccessToken, clearAccessToken } from '../lib/auth';
import { apiJson } from '../lib/api';
import { useEffect, useState } from 'react';

const glass =
  'rounded-2xl border border-zinc-300/50 bg-zinc-100/90 shadow-xl backdrop-blur-xl';

export function GlassNav() {
  const router = useRouter();
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    setIsLoggedIn(!!getAccessToken());
  }, []);

  async function handleLogout() {
    try {
      await apiJson('/api/auth/logout', { method: 'POST' });
    } catch {
      // ignore
    } finally {
      clearAccessToken();
      setIsLoggedIn(false);
      window.dispatchEvent(new CustomEvent('neurochtec:logout'));
      router.replace('/');
    }
  }

  return (
    <nav className={`flex items-center justify-between gap-4 ${glass} px-5 py-3`}>
      <Link href="/" className="flex items-center">
        <img
          src="/logo.png"
          alt="НейроЧтец"
          className="h-9 w-auto"
        />
      </Link>

      <div className="flex flex-1" aria-hidden />
      <div className="flex items-center gap-4">
        <Link
          href="/"
          className="text-sm font-medium text-zinc-700 hover:text-zinc-900"
        >
          Главная страница
        </Link>
        <Link
          href="/prices"
          className="text-sm font-medium text-zinc-700 hover:text-zinc-900"
        >
          Цены
        </Link>
        {isLoggedIn ? (
          <>
            <Link
              href="/app/projects"
              className="inline-flex items-center rounded-lg bg-[var(--color-accent)] px-4 py-2 text-sm font-medium text-zinc-900 hover:opacity-90"
            >
              В личный кабинет
            </Link>
            <button
              onClick={handleLogout}
              className="inline-flex items-center rounded-lg bg-[var(--color-secondary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Выйти
            </button>
          </>
        ) : (
          <Link
            href="/auth/login"
            className="inline-flex items-center rounded-lg bg-[var(--color-accent)] px-4 py-2 font-medium text-zinc-900 hover:opacity-90"
          >
            Войти
          </Link>
        )}
      </div>
    </nav>
  );
}
