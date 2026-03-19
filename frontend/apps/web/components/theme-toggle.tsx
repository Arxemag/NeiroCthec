'use client';

import { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import { Button } from './ui/button';
import { getTheme, toggleTheme, type Theme } from '@/lib/theme';

export function ThemeToggle() {
  const [theme, setThemeState] = useState<Theme>('dark');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setThemeState(getTheme());
    
    // Слушаем изменения темы из других компонентов
    const handleThemeChange = () => {
      setThemeState(getTheme());
    };
    
    // Используем MutationObserver для отслеживания изменений класса на html
    const observer = new MutationObserver(handleThemeChange);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    });
    
    return () => {
      observer.disconnect();
    };
  }, []);

  const handleToggle = () => {
    toggleTheme();
    // Обновляем состояние сразу после переключения
    setThemeState(getTheme());
  };

  if (!mounted) {
    return null;
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={handleToggle}
      aria-label="Переключить тему"
    >
      {theme === 'dark' ? (
        <Sun className="h-5 w-5" />
      ) : (
        <Moon className="h-5 w-5" />
      )}
    </Button>
  );
}
