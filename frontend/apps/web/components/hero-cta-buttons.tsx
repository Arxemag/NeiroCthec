'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getAccessToken } from '../lib/auth';

export function HeroCtaButtons() {
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    setIsLoggedIn(!!getAccessToken());
  }, []);

  useEffect(() => {
    const onLogout = () => setIsLoggedIn(!!getAccessToken());
    window.addEventListener('neurochtec:logout', onLogout);
    return () => window.removeEventListener('neurochtec:logout', onLogout);
  }, []);

  return (
    <div className="mt-8 flex flex-wrap gap-3">
      {!isLoggedIn && (
        <Link
          href="/auth/register"
          className="inline-flex items-center rounded-lg bg-indigo-500 px-4 py-2 font-medium text-white hover:bg-indigo-400"
        >
          Зарегистрироваться и попробовать
        </Link>
      )}
      {isLoggedIn && (
        <Link
          href="/app/projects"
          className="inline-flex items-center rounded-lg bg-[var(--color-accent)] px-4 py-2 font-medium text-zinc-900 hover:opacity-90"
        >
          Перейти в кабинет
        </Link>
      )}
    </div>
  );
}
