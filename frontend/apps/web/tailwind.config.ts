import type { Config } from 'tailwindcss';

export default {
  darkMode: ['class'],
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
    './app/globals.css',
  ],
  theme: {
    extend: {
      colors: {
        // Основные цвета из CSS variables
        primary: 'var(--color-primary)',
        surface: 'var(--color-surface)',
        surfaceSoft: 'var(--color-surface-soft)',
        
        text: 'var(--color-text)',
        textSecondary: 'var(--color-text-secondary)',
        textMuted: 'var(--color-text-muted)',
        
        accent: 'var(--color-accent)',
        accentWarm: 'var(--color-accent-warm)',
        accentSoft: 'var(--color-accent-soft)',
        
        border: 'var(--color-border)',
        
        // Обратная совместимость со старыми переменными (для постепенной миграции)
        background: 'var(--color-surface)',
        foreground: 'var(--color-text)',
        card: {
          DEFAULT: 'var(--color-surface-soft)',
          foreground: 'var(--color-text)',
        },
        secondary: {
          DEFAULT: 'var(--color-surface-soft)',
          foreground: 'var(--color-text-secondary)',
        },
        muted: {
          DEFAULT: 'var(--color-surface-soft)',
          foreground: 'var(--color-text-muted)',
        },
        destructive: {
          DEFAULT: '#EF4444',
          foreground: 'var(--color-text)',
        },
        input: 'var(--color-border)',
        ring: 'var(--color-accent)',
      },
      fontFamily: {
        heading: ['Manrope', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
      },
      borderRadius: {
        '2xl': '18px',
        lg: '12px',
        md: '8px',
        sm: '6px',
      },
      boxShadow: {
        'soft': '0 2px 8px rgba(0, 0, 0, 0.08)',
        'card': '0 4px 12px rgba(0, 0, 0, 0.1)',
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
} satisfies Config;
