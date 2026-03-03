'use client';

import { Container } from '../../components/ui';
import { Card } from '../../components/ui/card';
import { WavyBackgroundLayer } from '../../components/wavy-background-layer';
import { GlassNav } from '../../components/glass-nav';

export default function PricesPage() {

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
            <Card className="p-8 md:p-10">
              <h1 className="font-heading text-3xl font-semibold text-text">Цены</h1>
              <p className="mt-4 text-textSecondary">
                Страница с тарифами и подписками — в разработке.
              </p>
            </Card>
          </Container>
        </section>
      </div>
    </main>
  );
}
