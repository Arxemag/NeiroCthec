'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { clearAccessToken, getAccessToken } from '../lib/auth';
import { apiJson } from '../lib/api';
import { useEffect } from 'react';

function NavLink(props: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = pathname === props.href || pathname?.startsWith(props.href + '/');
  return (
    <Link
      href={props.href}
      className={`rounded-lg px-3 py-2 text-[var(--color-accent)] ${active ? 'bg-zinc-800 text-[var(--color-accent)]' : 'text-zinc-300 hover:bg-zinc-900'}`}
    >
      {props.children}
    </Link>
  );
}

export function AppShell(props: { children: React.ReactNode }) {
  const router = useRouter();

  useEffect(() => {
    // MVP guard: require token on client
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
      router.replace('/auth/login');
    }
  }

  return (
    <div className="min-h-screen">
      <div className="border-b border-zinc-800 bg-zinc-950">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="font-semibold">
            НейроЧтец
          </Link>
          <button onClick={logout} className="text-sm text-zinc-300 hover:text-zinc-50">
            Выйти
          </button>
        </div>
      </div>

      <div className="mx-auto grid max-w-6xl gap-6 px-6 py-6 md:grid-cols-[220px_1fr]">
        <aside className="rounded-2xl border border-zinc-800 bg-background p-3">
          <nav className="flex flex-col gap-1">
            <NavLink href="/app/projects">Проекты</NavLink>
            <NavLink href="/app/voices">Голоса</NavLink>
            <NavLink href="/app/subscription">Подписка</NavLink>
            <NavLink href="/app/profile">Профиль</NavLink>
          </nav>
        </aside>
        <main className="rounded-2xl border border-zinc-800 bg-neutral-light p-6">{props.children}</main>
      </div>
    </div>
  );
}

