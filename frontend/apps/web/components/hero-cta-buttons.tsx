'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { getAccessToken } from '../lib/auth';
import { Button } from './ui/button';

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
        <Button variant="primary" size="lg" asChild>
          <Link href="/auth/register">Зарегистрироваться и попробовать</Link>
        </Button>
      )}
      {isLoggedIn && (
        <Button variant="primary" size="lg" asChild>
          <Link href="/app/projects">Перейти в кабинет</Link>
        </Button>
      )}
    </div>
  );
}
