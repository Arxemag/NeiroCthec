import { Container, LinkButton } from '../components/ui';

export default function HomePage() {
  return (
    <main>
      <header className="border-b border-zinc-800">
        <Container>
          <div className="flex items-center justify-between py-5">
            <div className="text-lg font-semibold">НейроЧтец</div>
            <nav className="flex gap-3">
              <LinkButton variant="secondary" href="/auth/login">
                Войти
              </LinkButton>
              <LinkButton href="/auth/register">Зарегистрироваться и попробовать</LinkButton>
            </nav>
          </div>
        </Container>
      </header>

      <section className="py-16">
        <Container>
          <div className="grid gap-10 md:grid-cols-2 md:items-center">
            <div>
              <h1 className="text-4xl font-semibold tracking-tight">
                Текст → ИИ-голос → аудио
              </h1>
              <p className="mt-4 text-[#000000]">
                Озвучивайте книги, статьи и сценарии. Получайте результат быстро и слушайте прямо в браузере.
              </p>
              <div className="mt-8 flex gap-3">
                <LinkButton href="/auth/register">Зарегистрироваться и попробовать</LinkButton>
                <LinkButton variant="secondary" href="/app/projects">
                  Перейти в кабинет
                </LinkButton>
              </div>
            </div>
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
              <div className="text-sm text-zinc-400">Пример</div>
              <div className="mt-3 space-y-2 text-sm">
                <div className="rounded-lg bg-zinc-950/60 p-3">
                  <div className="text-zinc-300">1) Вставьте текст</div>
                  <div className="mt-2 text-zinc-500">«Добро пожаловать в НейроЧтец…»</div>
                </div>
                <div className="rounded-lg bg-zinc-950/60 p-3">
                  <div className="text-zinc-300">2) Выберите голоса</div>
                  <div className="mt-2 text-zinc-500">Анна (ru-RU), Максим (ru-RU)</div>
                </div>
                <div className="rounded-lg bg-zinc-950/60 p-3">
                  <div className="text-zinc-300">3) Получите озвучку</div>
                  <div className="mt-2 text-zinc-500">Стриминг в плеере, без прямых ссылок</div>
                </div>
              </div>
            </div>
          </div>
        </Container>
      </section>

      <section className="border-t border-zinc-800 py-14">
        <Container>
          <h2 className="text-2xl font-semibold">Как это работает</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-3">
            {[
              { title: 'Создайте проект', text: 'Загрузите или вставьте текст и выберите язык.' },
              { title: 'Выберите персонажей', text: 'Используйте один или несколько голосов между проектами.' },
              { title: 'Сгенерируйте и слушайте', text: 'Генерация идёт асинхронно, прослушивание — через стриминг.' },
            ].map((b) => (
              <div key={b.title} className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
                <div className="font-medium text-[var(--color-accent)]">{b.title}</div>
                <div className="mt-2 text-sm text-zinc-300">{b.text}</div>
              </div>
            ))}
          </div>
        </Container>
      </section>

      <section className="border-t border-zinc-800 py-14">
        <Container>
          <h2 className="text-2xl font-semibold">Сценарии использования</h2>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            {[
              { title: 'Авторы и издатели', text: 'Озвучка глав, тестирование повествования, аудиокниги.' },
              { title: 'Видео и реклама', text: 'Озвучка роликов, презентаций, креативов и объявлений.' },
            ].map((b) => (
              <div key={b.title} className="rounded-2xl border border-zinc-800 bg-zinc-900 p-6">
                <div className="font-medium text-[var(--color-accent)]">{b.title}</div>
                <div className="mt-2 text-sm text-zinc-300">{b.text}</div>
              </div>
            ))}
          </div>
        </Container>
      </section>

      <footer className="border-t border-zinc-800 py-10">
        <Container>
          <div className="flex flex-col gap-2 text-sm text-zinc-400 md:flex-row md:items-center md:justify-between">
            <div>© {new Date().getFullYear()} НейроЧтец</div>
            <div className="flex gap-4">
              <a className="hover:text-zinc-200" href="#">
                Политика
              </a>
              <a className="hover:text-zinc-200" href="#">
                Контакты
              </a>
              <a className="hover:text-zinc-200" href="#">
                FAQ
              </a>
            </div>
          </div>
        </Container>
      </footer>
    </main>
  );
}

