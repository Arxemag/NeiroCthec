'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { clearAccessToken, getAccessToken, setAccessToken } from '../lib/auth';
import { apiJson } from '../lib/api';
import { useEffect } from 'react';
import { useUser } from '../lib/use-user';
import { WavyBackgroundLayer } from './wavy-background-layer';

import { Card } from './ui/card';
import { Button } from './ui/button';
import { ThemeToggle } from './theme-toggle';

function NavLink(props: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = pathname === props.href || pathname?.startsWith(props.href + '/');
  return (
    <Link
      href={props.href}
      className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
        active 
          ? 'bg-surfaceSoft text-primary dark:text-accent' 
          : 'text-textSecondary hover:bg-surfaceSoft hover:text-text'
      }`}
    >
      {props.children}
    </Link>
  );
}

export function AppShell(props: { children: React.ReactNode }) {
  const router = useRouter();
  const { user, isLoading: isLoadingUser, isAdmin, error } = useUser();

  useEffect(() => {
    const token = getAccessToken();
    
    // Если нет токена, сразу редирект на страницу входа
    if (!token) {
      router.replace('/auth/login');
      return;
    }

    // Если загрузка завершена и есть ошибка (например, 401 Unauthorized), редирект на страницу входа
    if (!isLoadingUser && (error || !user)) {
      clearAccessToken();
      router.replace('/auth/login');
      return;
    }
  }, [router, isLoadingUser, user, error]);

  // Поддерживаем cookie для middleware: при валидной сессии без cookie выставляем (для старых сессий)
  useEffect(() => {
    const token = getAccessToken();
    if (token && typeof document !== 'undefined' && !document.cookie.includes('neurochtec_signed_in=1')) {
      setAccessToken(token);
    }
  }, [user]);

  async function logout() {
    try {
      await apiJson('/api/auth/logout', { method: 'POST' });
    } catch {
      // ignore
    } finally {
      clearAccessToken();
      router.replace('/');
    }
  }

  // Показываем загрузку или редирект, пока проверяется авторизация
  if (isLoadingUser) {
    return (
      <div className="relative min-h-screen bg-surface flex items-center justify-center">
        <div className="text-textSecondary">Загрузка...</div>
      </div>
    );
  }

  // Если нет пользователя или есть ошибка авторизации, показываем загрузку (редирект уже произойдет)
  if (!user || error) {
    return (
      <div className="relative min-h-screen bg-surface flex items-center justify-center">
        <div className="text-textSecondary">Перенаправление на страницу входа...</div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen bg-surface">
      <WavyBackgroundLayer />

      <div className="relative z-10 flex min-h-screen flex-col">
        <header className="px-4 pt-5">
          <div className="mx-auto flex max-w-6xl items-center gap-4">
            <Card className="flex w-full items-center gap-4 px-5 py-3">
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
                <Button variant="secondary" size="sm" onClick={logout}>
                  Выйти
                </Button>
              </div>
            </Card>
          </div>
        </header>

        <div className="mx-auto grid w-full max-w-6xl flex-1 gap-6 px-4 py-6 md:grid-cols-[220px_1fr]">
          <aside>
            <Card className="h-fit p-3">
              <nav className="flex flex-col gap-1">
                <NavLink href="/app/projects">Проекты</NavLink>
                <NavLink href="/app/books">Мои книги</NavLink>
                <NavLink href="/app/subscription">Подписка</NavLink>
                <NavLink href="/app/profile">Профиль</NavLink>
                <NavLink href="/app/admin/voices">Админка войса</NavLink>
                {!isLoadingUser && isAdmin && (
                  <NavLink href="/app/admin">Админ-панель</NavLink>
                )}
              </nav>
            </Card>
          </aside>
          <main>
            <Card className="min-h-0 p-6">{props.children}</Card>
          </main>
        </div>
      </div>
    </div>
  );
}
