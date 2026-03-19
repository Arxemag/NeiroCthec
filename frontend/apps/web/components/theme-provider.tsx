'use client';

import { useEffect } from 'react';
import { initTheme } from '../lib/theme';

/**
 * Компонент для инициализации темы при загрузке приложения
 * Должен быть размещен в root layout
 */
export function ThemeProvider() {
  useEffect(() => {
    initTheme();
  }, []);

  return null;
}
