import { Container } from '../../components/ui';
import { WavyBackgroundLayer } from '../../components/wavy-background-layer';
import { GlassNav } from '../../components/glass-nav';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="relative min-h-screen">
      <WavyBackgroundLayer />

      <div className="relative z-10 flex min-h-screen flex-col">
        <header className="px-4 pt-5">
          <Container>
            <GlassNav />
          </Container>
        </header>
        <div className="flex-1 px-4 py-12">
          <Container>{children}</Container>
        </div>
      </div>
    </main>
  );
}
