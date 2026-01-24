import { Container } from '../../components/ui';
import Link from 'next/link';

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <header className="border-b border-zinc-800">
        <Container>
          <div className="flex items-center justify-between py-5">
            <Link href="/" className="text-lg font-semibold">
              НейроЧтец
            </Link>
            <Link href="/" className="text-sm text-zinc-300 hover:text-zinc-100">
              На главную
            </Link>
          </div>
        </Container>
      </header>
      <main className="py-12">
        <Container>{children}</Container>
      </main>
    </div>
  );
}

