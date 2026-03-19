'use client';

import { useEffect, useState } from 'react';
import { WavyBackground } from './ui/wavy-background';
import { getTheme } from '../lib/theme';

export function WavyBackgroundLayer() {
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setTheme(getTheme());

    // Слушаем изменения темы
    const handleThemeChange = () => {
      setTheme(getTheme());
    };

    const observer = new MutationObserver(handleThemeChange);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class'],
    });

    return () => {
      observer.disconnect();
    };
  }, []);

  // Для темной темы используем темные цвета
  const darkColors = ['#1A1F2B', '#2A3140', '#3A4250', '#FFD600', '#1A1F2B'];
  const darkBackground = '#12141A'; // --color-surface

  // Для светлой темы используем светлые цвета
  const lightColors = ['#7A6CFF', '#9d93ff', '#c4b8ff', '#F5C542', '#7A6CFF'];
  const lightBackground = '#e9e5ff';

  const colors = theme === 'dark' ? darkColors : lightColors;
  const backgroundFill = theme === 'dark' ? darkBackground : lightBackground;
  
  // Используем inline стили для градиента, чтобы гарантировать правильное применение цветов
  const bgGradientStyle = theme === 'dark' 
    ? {
        background: `linear-gradient(to bottom right, var(--color-surface), var(--color-surface-soft), var(--color-surface))`,
      }
    : {
        background: 'linear-gradient(to bottom right, #e9e5ff, #f5f3ff, #fefce8)',
      };

  if (!mounted) {
    return (
      <div
        className="fixed inset-0 z-0 overflow-hidden"
        style={bgGradientStyle}
        aria-hidden
      />
    );
  }

  return (
    <div
      className="fixed inset-0 z-0 overflow-hidden"
      style={bgGradientStyle}
      aria-hidden
    >
      <WavyBackground
        containerClassName="absolute inset-0"
        colors={colors}
        backgroundFill={backgroundFill}
        waveOpacity={theme === 'dark' ? 0.3 : 0.78}
        blur={5}
        speed="slow"
        waveWidth={50}
      />
    </div>
  );
}
