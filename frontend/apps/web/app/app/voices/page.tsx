'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { Play } from 'lucide-react';
import { apiJson, API_BASE } from '../../../lib/api';
import { Button } from '../../../components/ui';
import { getAccessToken } from '../../../lib/auth';

type Voice = {
  id: string;
  name: string;
  gender: string;
  language: string;
  style: string;
  hasSample: boolean;
  characterDescription?: string | null;
};

export default function VoicesPage() {
  const [voices, setVoices] = useState<Voice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingSampleId, setLoadingSampleId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  const stopCurrent = useCallback(() => {
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.src = '';
      audioRef.current = null;
    }
  }, []);

  async function handlePlaySample(v: Voice) {
    if (!v.hasSample) return;
    stopCurrent();
    setLoadingSampleId(v.id);
    try {
      const token = getAccessToken();
      const res = await fetch(`${API_BASE}/api/voices/${v.id}/sample`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: 'include',
      });
      if (!res.ok) return;
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = stopCurrent;
      audio.onerror = stopCurrent;
      await audio.play();
    } catch {
      stopCurrent();
    } finally {
      setLoadingSampleId(null);
    }
  }

  useEffect(() => {
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current.src = '';
      }
    };
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiJson<{ voices: Voice[] }>('/api/voices');
        setVoices(data.voices);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Ошибка загрузки');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-text">Голосовые актеры</h1>
          <p className="mt-1 text-sm text-textSecondary">
            Доступные персонажи можно переиспользовать в разных проектах.
          </p>
        </div>
        <Button
          type="button"
          className="!bg-[var(--color-accent)] !text-zinc-900 hover:!opacity-90"
        >
          Создать нового персонажа озвучки
        </Button>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">
          {error}
        </div>
      )}

      <div className="mt-6">
        {loading ? (
          <div className="text-sm text-zinc-600">Загрузка…</div>
        ) : voices.length === 0 ? (
          <div className="rounded-xl border border-zinc-300/40 bg-zinc-100/60 py-8 text-center text-sm text-zinc-600">
            Нет доступных голосов.
          </div>
        ) : (
          <div className="overflow-hidden rounded-xl border border-zinc-300/40 bg-white/80">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-zinc-300/50 bg-zinc-100/70">
                  <th className="w-14 px-4 py-3 font-medium text-zinc-600" aria-label="Проигрывать" />
                  <th className="px-4 py-3 font-medium text-zinc-700">Имя</th>
                  <th className="px-4 py-3 font-medium text-zinc-700">Пол</th>
                  <th className="px-4 py-3 font-medium text-zinc-700">Стиль</th>
                  <th className="px-4 py-3 font-medium text-zinc-700">Описание характера</th>
                </tr>
              </thead>
              <tbody>
                {voices.map((v) => (
                  <tr
                    key={v.id}
                    className="border-b border-zinc-200/60 last:border-b-0 hover:bg-zinc-50/80"
                  >
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => handlePlaySample(v)}
                        disabled={!v.hasSample || loadingSampleId === v.id}
                        title={v.hasSample ? 'Прослушать пример' : 'Пример пока недоступен'}
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#7A6CFF]/15 text-[#7A6CFF] transition hover:bg-[#7A6CFF]/25 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-[#7A6CFF]/15"
                        aria-label={v.hasSample ? `Прослушать пример: ${v.name}` : `Пример для ${v.name} недоступен`}
                      >
                        {loadingSampleId === v.id ? (
                          <span className="h-4 w-4 animate-pulse rounded-full bg-current" />
                        ) : (
                          <Play className="h-4 w-4 shrink-0" fill="currentColor" />
                        )}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/app/voices/${v.id}`} className="font-medium text-[#7A6CFF] hover:underline">
                        {v.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-zinc-600">{v.gender}</td>
                    <td className="px-4 py-3 text-zinc-600">{v.style}</td>
                    <td className="max-w-xs px-4 py-3 text-zinc-600">{v.characterDescription ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
