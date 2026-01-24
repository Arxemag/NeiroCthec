import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'НейроЧтец',
  description: 'Текст → ИИ-голос → аудио. SaaS для авторов и частных пользователей.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className="min-h-screen ">
        {children}
      </body>
    </html>
  );
}

