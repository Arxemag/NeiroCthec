'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Check, X } from 'lucide-react';
import { apiJson } from '../../../../lib/api';
import { Button } from '../../../../components/ui';
import { useParams, useRouter } from 'next/navigation';

type Voice = {
  id: string;
  name: string;
  gender: string;
  language: string;
  style: string;
  hasSample: boolean;
  characterDescription?: string | null;
};

export default function VoiceCardPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const voiceId = params.id;

  const [voice, setVoice] = useState<Voice | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiJson<{ voice: Voice }>(`/api/voices/${voiceId}`);
      setVoice(data.voice);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [voiceId]);

  async function save() {
    if (!voice) return;
    setSaving(true);
    setError(null);
    try {
      await apiJson<{ voice: Voice }>(`/api/voices/${voiceId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: voice.name,
          characterDescription: voice.characterDescription ?? null,
        }),
      });
      router.push('/app/voices');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Не удалось сохранить');
    } finally {
      setSaving(false);
    }
  }

  async function deleteVoice() {
    setShowDeleteConfirm(false);
    setDeleting(true);
    setError(null);
    try {
      await apiJson(`/api/voices/${voiceId}`, { method: 'DELETE' });
      router.push('/app/voices');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Не удалось удалить');
    } finally {
      setDeleting(false);
    }
  }

  if (loading) return <div className="text-sm text-zinc-600">Загрузка…</div>;
  if (!voice) return <div className="text-sm text-zinc-600">Персонаж не найден</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Link href="/app/voices" className="text-sm text-[#7A6CFF] hover:underline">
            ← К списку голосовых актёров
          </Link>
          <h1 className="mt-2 text-2xl font-semibold text-[var(--color-primary)]">Карточка персонажа</h1>
          <p className="mt-1 text-sm text-zinc-600">
            Пол: {voice.gender} · Стиль: {voice.style}
          </p>
        </div>
        <Button variant="secondary" disabled={saving} onClick={save}>
          {saving ? 'Сохраняем…' : 'Сохранить'}
        </Button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>
      )}

      <div className="rounded-2xl border border-zinc-300/40 bg-zinc-100/80 p-6 space-y-6">
        <div>
          <label className="block text-sm font-medium text-zinc-700">Имя</label>
          <input
            type="text"
            value={voice.name}
            onChange={(e) => setVoice({ ...voice, name: e.target.value })}
            className="mt-2 w-full rounded-lg border border-zinc-300/40 bg-zinc-200/90 px-3 py-2 text-zinc-900 outline-none focus:border-[#7A6CFF]"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-zinc-700">Описание характера</label>
          <textarea
            value={voice.characterDescription ?? ''}
            onChange={(e) => setVoice({ ...voice, characterDescription: e.target.value || null })}
            rows={4}
            className="mt-2 w-full resize-y rounded-lg border border-zinc-300/40 bg-zinc-200/90 px-3 py-2 text-zinc-900 outline-none focus:border-[#7A6CFF]"
            placeholder="Опишите характер персонажа…"
          />
        </div>
      </div>

      <div className="flex justify-end">
        {showDeleteConfirm ? (
          <div className="flex items-center gap-1 rounded-lg border border-red-200 bg-red-50/80 overflow-hidden">
            <button
              type="button"
              onClick={deleteVoice}
              disabled={deleting}
              className="flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
              aria-label="Подтвердить удаление"
            >
              <Check className="h-3.5 w-3.5" />
              Подтвердить
            </button>
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(false)}
              disabled={deleting}
              className="flex items-center gap-1 border-l border-red-200 px-2 py-1.5 text-xs font-medium text-zinc-600 hover:bg-zinc-100 disabled:opacity-50"
              aria-label="Отменить удаление"
            >
              <X className="h-3.5 w-3.5" />
              Отменить
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setShowDeleteConfirm(true)}
            disabled={deleting}
            className="text-sm font-medium text-red-600 hover:text-red-700 hover:underline disabled:opacity-50"
            aria-label="Удалить персонажа"
          >
            Удалить персонажа
          </button>
        )}
      </div>
    </div>
  );
}
