'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { getAccessToken, clearAccessToken } from '../lib/auth';
import { apiJson } from '../lib/api';
import { useEffect, useState } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { ThemeToggle } from './theme-toggle';

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
    <Card className="flex items-center justify-between gap-4 px-5 py-3">
      <Link href="/" className="flex items-center gap-2">
        <img
          src="/logo.svg"
          alt="НейроЧтец"
          className="h-12 w-auto min-h-[48px]"
        />
        <span className="font-heading text-lg font-semibold text-text hidden md:block whitespace-nowrap">
          НейроЧтец
        </span>
      </Link>

      <div className="flex flex-1" aria-hidden />
      <div className="flex items-center gap-4">
        <Link
          href="/"
          className="text-sm font-medium text-textSecondary hover:text-text transition-colors"
        >
          Главная страница
        </Link>
        <Link
          href="/prices"
          className="text-sm font-medium text-textSecondary hover:text-text transition-colors"
        >
          Цены
        </Link>
        <ThemeToggle />
        {isLoggedIn ? (
          <>
            <Button variant="primary" size="sm" asChild>
              <Link href="/app/projects">В личный кабинет</Link>
            </Button>
            <Button variant="secondary" size="sm" onClick={handleLogout}>
              Выйти
            </Button>
          </>
        ) : (
          <Button variant="primary" size="sm" asChild>
            <Link href="/auth/login">Войти</Link>
          </Button>
        )}
      </div>
    </Card>
  );
}
