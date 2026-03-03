# Дизайн-система НейроЧтец

## 🎨 Цветовая система

Все цвета определены через CSS variables и автоматически переключаются между dark и light темами.

### Использование в Tailwind

```tsx
// Фоны
<div className="bg-surface">Основной фон</div>
<div className="bg-surface-soft">Мягкий фон для карточек</div>

// Текст
<p className="text-text">Основной текст</p>
<p className="text-text-secondary">Вторичный текст</p>
<p className="text-text-muted">Приглушенный текст</p>

// Акценты
<button className="bg-accent text-primary">Акцентная кнопка</button>
<span className="text-accent-warm">Теплый акцент</span>

// Границы
<div className="border border-border">Граница</div>
```

### CSS Variables

**Dark Theme (по умолчанию):**
- `--color-primary: #0A0A0A`
- `--color-surface: #12141A`
- `--color-surface-soft: #1A1F2B`
- `--color-text: #F5F7FA`
- `--color-text-secondary: #A3A9B8`
- `--color-text-muted: #6B7280`
- `--color-accent: #FFD600`
- `--color-accent-warm: #FFB300`
- `--color-border: #2A3140`

**Light Theme:**
- `--color-primary: #111827`
- `--color-surface: #FFFFFF`
- `--color-surface-soft: #F3F4F6`
- `--color-text: #111827`
- `--color-text-secondary: #6B7280`
- `--color-text-muted: #9CA3AF`
- `--color-accent: #FFD600`
- `--color-accent-warm: #F59E0B`
- `--color-border: #E5E7EB`

## 📝 Типографика

### Шрифты

- **Manrope** — для заголовков (h1-h6)
- **Inter** — для основного текста

### Использование

```tsx
<h1 className="font-heading">Заголовок</h1>
<p className="font-body">Основной текст</p>
```

## 🧩 Компоненты

### Button

```tsx
import { Button } from '@/components/ui/button';

// Варианты
<Button variant="primary">Primary</Button>
<Button variant="secondary">Secondary</Button>
<Button variant="ghost">Ghost</Button>
<Button variant="outline">Outline</Button>

// Размеры
<Button size="sm">Small</Button>
<Button size="default">Default</Button>
<Button size="lg">Large</Button>
```

### Card

```tsx
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';

<Card>
  <CardHeader>
    <CardTitle>Заголовок</CardTitle>
    <CardDescription>Описание</CardDescription>
  </CardHeader>
  <CardContent>
    Контент карточки
  </CardContent>
  <CardFooter>
    <Button>Действие</Button>
  </CardFooter>
</Card>
```

### Container

```tsx
import { Container } from '@/components/ui/container';

<Container>
  Контент с максимальной шириной 1200px и адаптивными отступами
</Container>

// С кастомной шириной
<Container maxWidth="lg">
  Контент с шириной 1400px
</Container>
```

## 🌗 Переключение темы

### Программно

```tsx
import { setTheme, getTheme, toggleTheme } from '@/lib/theme';

// Установить тему
setTheme('light');
setTheme('dark');

// Получить текущую тему
const currentTheme = getTheme();

// Переключить тему
toggleTheme();
```

### Компонент переключателя

```tsx
import { ThemeToggle } from '@/components/theme-toggle';

<ThemeToggle />
```

### В HTML

Для маркетинговых страниц добавьте класс `light` на `<html>`:

```tsx
<html lang="ru" className="light">
```

## 📐 Правила использования

### ✅ Правильно

```tsx
// Использование CSS variables через Tailwind
<div className="bg-surface text-text">
  <Button variant="primary">Кнопка</Button>
</div>

// Использование компонентов
<Card>
  <CardContent>Контент</CardContent>
</Card>
```

### ❌ Неправильно

```tsx
// Захардкоженные цвета
<div className="bg-[#12141A] text-[#F5F7FA]">❌</div>

// Прямое использование HEX
<div style={{ backgroundColor: '#FFD600' }}>❌</div>
```

## 🎯 Примеры

См. `/app/example-design-system/page.tsx` для полного примера использования всех компонентов.

## 📚 Дополнительные ресурсы

- Все компоненты находятся в `components/ui/`
- Утилиты темы в `lib/theme.ts`
- CSS variables определены в `app/globals.css`
- Tailwind конфигурация в `tailwind.config.ts`
