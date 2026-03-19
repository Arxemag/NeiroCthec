'use client';

import { useState } from 'react';
import { Button } from '../../../components/ui';
import Link from 'next/link';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    // Заглушка: без запроса к API и почтового сервера
    setTimeout(() => {
      setSent(true);
      setLoading(false);
    }, 400);
  }

  if (sent) {
    return (
      <div className="mx-auto max-w-md rounded-2xl border border-zinc-300/50 bg-zinc-100/90 p-6 shadow-xl backdrop-blur-xl">
        <h1 className="text-2xl font-semibold text-[var(--color-primary)]">Восстановление пароля</h1>
        <p className="mt-4 text-sm text-zinc-600">
          Если аккаунт с email <strong className="text-zinc-800">{email}</strong> существует, на него будет
          отправлена ссылка для сброса пароля.
        </p>
        <p className="mt-2 text-sm text-zinc-500 italic">
          Заглушка: почтовый сервер не настроен, письмо не отправляется.
        </p>
        <Link
          href="/auth/login"
          className="mt-6 inline-block text-sm font-medium text-[#7A6CFF] hover:underline"
        >
          ← Вернуться ко входу
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md rounded-2xl border border-zinc-300/50 bg-zinc-100/90 p-6 shadow-xl backdrop-blur-xl">
      <h1 className="text-2xl font-semibold text-[var(--color-primary)]">Восстановление пароля</h1>
      <p className="mt-2 text-sm text-zinc-600">
        Введите email — мы отправим ссылку для сброса пароля.
      </p>

      <form className="mt-6 space-y-4" onSubmit={onSubmit}>
        <div>
          <label className="text-sm text-zinc-700">Email</label>
          <input
            className="mt-1 w-full rounded-lg border border-zinc-300/40 bg-zinc-100/80 px-3 py-2 text-zinc-900 outline-none focus:border-[#7A6CFF]"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            required
          />
        </div>

        <Button
          disabled={loading}
          type="submit"
          className="w-full !bg-[var(--color-accent)] !text-[var(--color-primary)]"
        >
          {loading ? 'Отправка…' : 'Отправить ссылку'}
        </Button>
      </form>

      <Link
        href="/auth/login"
        className="mt-4 inline-block text-sm text-[#7A6CFF] hover:underline"
      >
        ← Вернуться ко входу
      </Link>
    </div>
  );
}
