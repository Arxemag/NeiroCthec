'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { clearAccessToken, getAccessToken } from '../lib/auth';
import { apiJson } from '../lib/api';
import { useEffect } from 'react';
import { WavyBackgroundLayer } from './wavy-background-layer';

const glass = 'rounded-2xl border border-zinc-300/50 bg-zinc-100/90 shadow-xl backdrop-blur-xl';
const glassCard = 'rounded-2xl border border-zinc-300/40 bg-zinc-100/80 backdrop-blur-lg';

function NavLink(props: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = pathname === props.href || pathname?.startsWith(props.href + '/');
  return (
    <Link
      href={props.href}
      className={`rounded-lg px-3 py-2 text-sm font-medium ${active ? 'bg-zinc-200/60 text-[#7A6CFF]' : 'text-zinc-700 hover:bg-zinc-200/40 hover:text-zinc-900'}`}
    >
      {props.children}
    </Link>
  );
}

export function AppShell(props: { children: React.ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    const token = getAccessToken();
    if (!token) router.replace('/auth/login');
  }, [router]);

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

  return (
    <div className="relative min-h-screen">
      <WavyBackgroundLayer />

      <div className="relative z-10 flex min-h-screen flex-col">
        <header className="px-4 pt-5">
          <div className={`mx-auto flex max-w-6xl items-center gap-4 ${glass} px-5 py-3`}>
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
              <button
                onClick={logout}
                className="rounded-lg bg-[var(--color-secondary)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
              >
                Выйти
              </button>
            </div>
          </div>
        </header>

        <div className="mx-auto grid w-full max-w-6xl flex-1 gap-6 px-4 py-6 md:grid-cols-[220px_1fr]">
          <aside className={`${glassCard} h-fit p-3`}>
            <nav className="flex flex-col gap-1">
              <NavLink href="/app/projects">Проекты</NavLink>
              <NavLink href="/app/voices">Голосовые актеры</NavLink>
              <NavLink href="/app/subscription">Подписка</NavLink>
              <NavLink href="/app/profile">Профиль</NavLink>
              <NavLink href="/app/admin">Админ-панель</NavLink>
            </nav>
          </aside>
          <main className={`${glass} min-h-0 p-6`}>{props.children}</main>
        </div>
      </div>
    </div>
  );
}
