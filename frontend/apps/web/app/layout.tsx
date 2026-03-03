import './globals.css';
import type { Metadata } from 'next';
import { ThemeProvider } from '../components/theme-provider';

export const metadata: Metadata = {
  title: 'НейроЧтец',
  description: 'Текст → ИИ-голос → аудио. SaaS для авторов и частных пользователей.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru" className="dark" suppressHydrationWarning>
      <body className="min-h-screen bg-surface text-text font-body antialiased">
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('neurochtec-theme');
                  if (theme === 'light' || theme === 'dark') {
                    document.documentElement.classList.remove('dark', 'light');
                    document.documentElement.classList.add(theme);
                  }
                } catch (e) {}
              })();
            `,
          }}
        />
        <ThemeProvider />
        {children}
      </body>
    </html>
  );
}
