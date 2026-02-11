import { Container } from '../components/ui';
import { WavyBackgroundLayer } from '../components/wavy-background-layer';
import { GlassNav } from '../components/glass-nav';
import { HeroCtaButtons } from '../components/hero-cta-buttons';

const glass = 'rounded-2xl border border-zinc-300/50 bg-zinc-100/90 shadow-xl backdrop-blur-xl';
const glassCard = 'rounded-2xl border border-zinc-300/40 bg-zinc-100/80 backdrop-blur-lg';

export default function HomePage() {
  return (
    <main className="relative min-h-screen">
      <WavyBackgroundLayer />

      <div className="relative z-10 flex min-h-screen flex-col">
        <header className="px-4 pt-5">
          <Container>
            <GlassNav />
          </Container>
        </header>

        <section className="flex-1 px-4 py-14 md:py-20">
          <Container>
            <div className={`grid gap-10 md:grid-cols-2 md:items-center ${glass} p-8 md:p-10`}>
              <div>
                <h1 className="text-4xl font-semibold tracking-tight text-zinc-900">
                  Текст → ИИ-голос → аудио
                </h1>
                <p className="mt-4 text-zinc-700">
                  Озвучивайте книги, статьи и сценарии. Получайте результат
                  быстро и слушайте прямо в браузере.
                </p>
                <HeroCtaButtons />
              </div>
              <div className="rounded-2xl border border-zinc-600/60 bg-zinc-800/95 p-6 backdrop-blur-lg">
                <div className="text-sm font-medium text-zinc-300">Пример</div>
                <div className="mt-3 space-y-2 text-sm">
                  <div className="rounded-lg border border-zinc-600/50 bg-zinc-700/80 p-3">
                    <div className="text-zinc-100">1) Вставьте текст</div>
                    <div className="mt-2 text-zinc-400">«Добро пожаловать в НейроЧтец…»</div>
                  </div>
                  <div className="rounded-lg border border-zinc-600/50 bg-zinc-700/80 p-3">
                    <div className="text-zinc-100">2) Выберите голоса</div>
                    <div className="mt-2 text-zinc-400">Анна (ru-RU), Максим (ru-RU)</div>
                  </div>
                  <div className="rounded-lg border border-zinc-600/50 bg-zinc-700/80 p-3">
                    <div className="text-zinc-100">3) Получите озвучку</div>
                    <div className="mt-2 text-zinc-400">Стриминг в плеере, без прямых ссылок</div>
                  </div>
                </div>
              </div>
            </div>
          </Container>
        </section>

        <section className="px-4 py-12">
          <Container>
            <div className={`${glass} p-8`}>
              <h2 className="text-2xl font-semibold text-zinc-900">Как это работает</h2>
              <div className="mt-6 grid gap-4 md:grid-cols-3">
                {[
                  { title: 'Создайте проект', text: 'Загрузите или вставьте текст и выберите язык.' },
                  { title: 'Выберите персонажей', text: 'Используйте один или несколько голосов между проектами.' },
                  { title: 'Сгенерируйте и слушайте', text: 'Генерация идёт асинхронно, прослушивание — через стриминг.' },
                ].map((b) => (
                  <div key={b.title} className={`${glassCard} p-6`}>
                    <div className="font-medium text-[#7A6CFF]">{b.title}</div>
                    <div className="mt-2 text-sm text-zinc-600">{b.text}</div>
                  </div>
                ))}
              </div>
            </div>
          </Container>
        </section>

        <section className="px-4 py-12">
          <Container>
            <div className={`${glass} p-8`}>
              <h2 className="text-2xl font-semibold text-zinc-900">Сценарии использования</h2>
              <div className="mt-6 grid gap-4 md:grid-cols-2">
                {[
                  { title: 'Авторы и издатели', text: 'Озвучка глав, тестирование повествования, аудиокниги.' },
                  { title: 'Видео и реклама', text: 'Озвучка роликов, презентаций, креативов и объявлений.' },
                ].map((b) => (
                  <div key={b.title} className={`${glassCard} p-6`}>
                    <div className="font-medium text-[#7A6CFF]">{b.title}</div>
                    <div className="mt-2 text-sm text-zinc-600">{b.text}</div>
                  </div>
                ))}
              </div>
            </div>
          </Container>
        </section>

        <footer className="mt-auto px-4 py-8">
          <Container>
            <div className="flex flex-col gap-2 rounded-2xl border border-zinc-300/40 bg-zinc-100/80 px-6 py-4 text-sm backdrop-blur-lg md:flex-row md:items-center md:justify-between">
              <div className="text-zinc-600">© {new Date().getFullYear()} НейроЧтец</div>
              <div className="flex gap-4">
                <a className="text-zinc-600 hover:text-zinc-900" href="#">Политика</a>
                <a className="text-zinc-600 hover:text-zinc-900" href="#">Контакты</a>
                <a className="text-zinc-600 hover:text-zinc-900" href="#">FAQ</a>
              </div>
            </div>
          </Container>
        </footer>
      </div>
    </main>
  );
}
