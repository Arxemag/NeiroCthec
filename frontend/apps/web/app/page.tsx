'use client';

import { Container } from '../components/ui';
import { Card, CardContent } from '../components/ui/card';
import { WavyBackgroundLayer } from '../components/wavy-background-layer';
import { GlassNav } from '../components/glass-nav';
import { HeroCtaButtons } from '../components/hero-cta-buttons';

export default function HomePage() {

  return (
    <main className="relative min-h-screen bg-surface">
      <WavyBackgroundLayer />

      <div className="relative z-10 flex min-h-screen flex-col">
        <header className="px-4 pt-5">
          <Container>
            <GlassNav />
          </Container>
        </header>

        <section className="flex-1 px-4 py-14 md:py-20">
          <Container>
            <Card className="grid gap-10 md:grid-cols-2 md:items-center p-8 md:p-10">
              <div>
                <h1 className="font-heading text-4xl font-semibold tracking-tight text-text">
                  Текст → ИИ-голос → аудио
                </h1>
                <p className="mt-4 text-textSecondary">
                  Озвучивайте книги, статьи и сценарии. Получайте результат
                  быстро и слушайте прямо в браузере.
                </p>
                <HeroCtaButtons />
              </div>
              <Card className="border-border bg-surfaceSoft p-6">
                <div className="text-sm font-medium text-textSecondary">Пример</div>
                <div className="mt-3 space-y-2 text-sm">
                  <Card className="border-border bg-surface p-3">
                    <div className="text-text">1) Вставьте текст</div>
                    <div className="mt-2 text-textMuted">«Добро пожаловать в НейроЧтец…»</div>
                  </Card>
                  <Card className="border-border bg-surface p-3">
                    <div className="text-text">2) Выберите голоса</div>
                    <div className="mt-2 text-textMuted">Анна (ru-RU), Максим (ru-RU)</div>
                  </Card>
                  <Card className="border-border bg-surface p-3">
                    <div className="text-text">3) Получите озвучку</div>
                    <div className="mt-2 text-textMuted">Стриминг в плеере, без прямых ссылок</div>
                  </Card>
                </div>
              </Card>
            </Card>
          </Container>
        </section>

        <section className="px-4 py-12">
          <Container>
            <Card className="p-8">
              <h2 className="font-heading text-2xl font-semibold text-text">Как это работает</h2>
              <div className="mt-6 grid gap-4 md:grid-cols-3">
                {[
                  { title: 'Создайте проект', text: 'Загрузите или вставьте текст и выберите язык.' },
                  { title: 'Выберите персонажей', text: 'Используйте один или несколько голосов между проектами.' },
                  { title: 'Сгенерируйте и слушайте', text: 'Генерация идёт асинхронно, прослушивание — через стриминг.' },
                ].map((b) => (
                  <Card key={b.title} className="p-6">
                    <CardContent className="p-0">
                      <div className="font-medium text-primary dark:text-text">{b.title}</div>
                      <div className="mt-2 text-sm text-textSecondary">{b.text}</div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </Card>
          </Container>
        </section>

        <section className="px-4 py-12">
          <Container>
            <Card className="p-8">
              <h2 className="font-heading text-2xl font-semibold text-text">Сценарии использования</h2>
              <div className="mt-6 grid gap-4 md:grid-cols-2">
                {[
                  { title: 'Авторы и издатели', text: 'Озвучка глав, тестирование повествования, аудиокниги.' },
                  { title: 'Видео и реклама', text: 'Озвучка роликов, презентаций, креативов и объявлений.' },
                ].map((b) => (
                  <Card key={b.title} className="p-6">
                    <CardContent className="p-0">
                      <div className="font-medium text-primary dark:text-text">{b.title}</div>
                      <div className="mt-2 text-sm text-textSecondary">{b.text}</div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </Card>
          </Container>
        </section>

        <footer className="mt-auto px-4 py-8">
          <Container>
            <Card className="px-6 py-4">
              <div className="flex flex-col gap-2 text-sm md:flex-row md:items-center md:justify-between">
                <div className="text-textSecondary">© {new Date().getFullYear()} НейроЧтец</div>
                <div className="flex gap-4">
                  <a className="text-textSecondary hover:text-text transition-colors" href="#">Политика</a>
                  <a className="text-textSecondary hover:text-text transition-colors" href="#">Контакты</a>
                  <a className="text-textSecondary hover:text-text transition-colors" href="#">FAQ</a>
                </div>
              </div>
            </Card>
          </Container>
        </footer>
      </div>
    </main>
  );
}
