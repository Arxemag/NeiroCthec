'use client';

import { Container } from '@/components/ui/container';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Hero } from '@/components/hero';
import { ThemeToggle } from '@/components/theme-toggle';
import { setTheme } from '@/lib/theme';
import { useEffect } from 'react';

/**
 * Пример страницы с mixed theme
 * Демонстрирует использование новой дизайн-системы
 */
export default function DesignSystemExamplePage() {
  useEffect(() => {
    // Пример: маркетинговая страница использует светлую тему
    setTheme('light');
    
    return () => {
      // Возвращаем темную тему при размонтировании
      setTheme('dark');
    };
  }, []);

  return (
    <div className="min-h-screen bg-surface">
      {/* Header с переключателем темы */}
      <header className="border-b border-border bg-surfaceSoft">
        <Container className="flex items-center justify-between py-4">
          <h2 className="font-heading text-xl font-bold text-text">Пример дизайн-системы</h2>
          <ThemeToggle />
        </Container>
      </header>

      {/* Hero блок */}
      <Hero
        title="НейроЧтец — ИИ-озвучка текста"
        description="Превращайте текст в естественную речь с помощью искусственного интеллекта. Технологичный интерфейс для работы с текстом и аудио."
        primaryAction={{
          label: 'Начать работу',
          href: '/app/projects',
        }}
        secondaryAction={{
          label: 'Узнать больше',
          href: '/prices',
        }}
      />

      {/* Примеры компонентов */}
      <section className="py-16">
        <Container>
          <h2 className="font-heading text-3xl font-bold mb-8 text-text">Компоненты системы</h2>
          
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {/* Кнопки */}
            <Card>
              <CardHeader>
                <CardTitle>Кнопки</CardTitle>
                <CardDescription>Варианты кнопок с разными стилями</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button variant="primary" className="w-full">Primary</Button>
                <Button variant="secondary" className="w-full">Secondary</Button>
                <Button variant="ghost" className="w-full">Ghost</Button>
                <Button variant="outline" className="w-full">Outline</Button>
              </CardContent>
            </Card>

            {/* Размеры кнопок */}
            <Card>
              <CardHeader>
                <CardTitle>Размеры</CardTitle>
                <CardDescription>Разные размеры компонентов</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <Button size="sm">Small</Button>
                <Button size="default">Default</Button>
                <Button size="lg">Large</Button>
              </CardContent>
            </Card>

            {/* Типографика */}
            <Card>
              <CardHeader>
                <CardTitle>Типографика</CardTitle>
                <CardDescription>Шрифты Manrope и Inter</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <h3 className="font-heading text-lg font-semibold text-text mb-1">Заголовок</h3>
                  <p className="font-body text-textSecondary text-sm">Основной текст с использованием Inter</p>
                </div>
                <div>
                  <p className="text-textMuted text-xs">Приглушенный текст</p>
                </div>
              </CardContent>
            </Card>

            {/* Цвета */}
            <Card>
              <CardHeader>
                <CardTitle>Цветовая система</CardTitle>
                <CardDescription>CSS variables для тем</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded bg-accent" />
                  <span className="text-sm text-textSecondary">Accent</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded bg-accentWarm" />
                  <span className="text-sm text-textSecondary">Accent Warm</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded bg-surfaceSoft border border-border" />
                  <span className="text-sm text-textSecondary">Surface Soft</span>
                </div>
              </CardContent>
            </Card>

            {/* Карточки */}
            <Card>
              <CardHeader>
                <CardTitle>Карточка</CardTitle>
                <CardDescription>Компонент Card с разными секциями</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-textSecondary text-sm">
                  Контент карточки с использованием цветов из дизайн-системы.
                </p>
              </CardContent>
              <CardFooter>
                <Button variant="ghost" size="sm">Действие</Button>
              </CardFooter>
            </Card>

            {/* Контейнер */}
            <Card>
              <CardHeader>
                <CardTitle>Контейнер</CardTitle>
                <CardDescription>Адаптивные отступы и центрирование</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="rounded-lg bg-surface border border-border p-4">
                  <p className="text-xs text-textMuted">
                    Максимальная ширина: 1200px<br />
                    Отступы: responsive
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </Container>
      </section>

      {/* Пример использования в реальном интерфейсе */}
      <section className="py-16 bg-surfaceSoft">
        <Container>
          <h2 className="font-heading text-3xl font-bold mb-8 text-text">Пример интерфейса</h2>
          
          <Card className="max-w-2xl mx-auto">
            <CardHeader>
              <CardTitle>Загрузка файлов проекта</CardTitle>
              <CardDescription>
                Пример использования компонентов в реальном интерфейсе
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="rounded-xl border-2 border-dashed border-border bg-surfaceSoft p-8 text-center">
                <p className="text-textSecondary mb-4">
                  Перетащите файлы сюда или нажмите для выбора
                </p>
                <Button variant="secondary">Выбрать файлы</Button>
              </div>
              
              <div className="flex gap-2">
                <Button variant="primary" className="flex-1">
                  Загрузить на сервер
                </Button>
                <Button variant="outline">
                  Отмена
                </Button>
              </div>
            </CardContent>
          </Card>
        </Container>
      </section>

      {/* Footer */}
      <footer className="border-t border-border bg-surfaceSoft py-8 mt-16">
        <Container>
          <div className="flex flex-col md:flex-row justify-between items-center gap-4 text-sm text-textSecondary">
            <div>© {new Date().getFullYear()} НейроЧтец</div>
            <div className="flex gap-6">
              <a href="#" className="hover:text-text transition-colors">Документация</a>
              <a href="#" className="hover:text-text transition-colors">Поддержка</a>
            </div>
          </div>
        </Container>
      </footer>
    </div>
  );
}
