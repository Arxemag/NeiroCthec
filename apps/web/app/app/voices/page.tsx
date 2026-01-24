'use client';

import { useEffect, useState } from 'react';
import { apiJson } from '../../../lib/api';

type Voice = {
  id: string;
  name: string;
  gender: string;
  language: string;
  style: string;
  hasSample: boolean;
};

export default function VoicesPage() {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiJson<{ voices: Voice[] }>('/api/voices');
        setVoices(data.voices);
      } catch (e: any) {
        setError(e?.message ?? 'Ошибка загрузки');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-semibold">Голоса</h1>
      <p className="mt-1 text-sm text-zinc-300">Доступные персонажи можно переиспользовать в разных проектах.</p>

      {error && <div className="mt-4 rounded-lg border border-red-900 bg-red-950/40 p-3 text-sm text-red-200">{error}</div>}

      <div className="mt-6">
        {loading ? (
          <div className="text-sm text-zinc-300">Загрузка…</div>
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {voices.map((v) => (
              <div key={v.id} className="rounded-2xl border border-zinc-800 bg-zinc-950/40 p-4">
                <div className="font-medium">{v.name}</div>
                <div className="mt-1 text-sm text-zinc-400">
                  {v.language} · {v.gender} · {v.style}
                </div>
                <div className="mt-3 text-xs text-zinc-500">
                  Пример: {v.hasSample ? 'доступен (через /api/voices/:id/sample)' : 'пока нет (MVP)'}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

