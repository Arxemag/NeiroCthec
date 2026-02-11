import { Container } from '../../components/ui';
import { WavyBackgroundLayer } from '../../components/wavy-background-layer';
import { GlassNav } from '../../components/glass-nav';

const glass = 'rounded-2xl border border-zinc-300/50 bg-zinc-100/90 shadow-xl backdrop-blur-xl';

export default function PricesPage() {
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
            <div className={`${glass} p-8 md:p-10`}>
              <h1 className="text-3xl font-semibold text-zinc-900">Цены</h1>
              <p className="mt-4 text-zinc-600">
                Страница с тарифами и подписками — в разработке.
              </p>
            </div>
          </Container>
        </section>
      </div>
    </main>
  );
}
