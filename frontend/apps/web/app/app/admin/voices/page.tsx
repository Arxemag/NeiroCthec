'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { getAppApiVoiceSampleUrl, listVoices, uploadVoice, deleteVoice, type AppVoice } from '../../../../lib/app-api';

const glass = 'rounded-2xl border border-zinc-300/50 bg-zinc-100/90 shadow-xl backdrop-blur-xl';
const glassCard = 'rounded-2xl border border-zinc-300/40 bg-zinc-100/80 backdrop-blur-lg';

const BUILTIN_IDS = new Set(['narrator', 'male', 'female']);

export default function AdminVoicesPage() {
  const [voices, setVoices] = useState<AppVoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const sorted = useMemo(() => {
    return [...voices].sort((a, b) => a.name.localeCompare(b.name));
  }, [voices]);

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const data = await listVoices();
      setVoices(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка загрузки голосов');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  async function handleUpload() {
    if (!selectedFile) return;
    setUploading(true);
    setUploadError(null);
    try {
      await uploadVoice(selectedFile);
      setSelectedFile(null);
      await reload();
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : 'Ошибка загрузки');
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(id: string) {
    if (!id || BUILTIN_IDS.has(id)) return;
    try {
      await deleteVoice(id);
      await reload();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Ошибка удаления');
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-text">Админ-панель — Голоса</h1>
          <p className="mt-1 text-sm text-textSecondary">Управление voice samples (доступно всем, позже ограничим)</p>
        </div>
        <Link
          href="/app/admin"
          className="inline-flex items-center rounded-lg bg-zinc-800 px-4 py-2 font-medium text-zinc-50 hover:bg-zinc-700"
        >
          Метрики
        </Link>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>
      )}

      <div className={`${glass} p-6 space-y-4`}>
        <h2 className="text-lg font-semibold text-zinc-800">Загрузка нового голоса (WAV, до 30 секунд)</h2>
        <div className={`${glassCard} p-4 space-y-3`}>
          <input
            type="file"
            accept=".wav,audio/wav"
            onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
          />
          <div className="flex gap-3">
            <button
              type="button"
              disabled={!selectedFile || uploading}
              onClick={handleUpload}
              className="inline-flex items-center rounded-lg bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-50 hover:bg-zinc-700 disabled:opacity-50"
            >
              {uploading ? 'Загрузка…' : 'Загрузить'}
            </button>
            {uploadError && <div className="text-sm text-red-700">{uploadError}</div>}
          </div>
        </div>
      </div>

      <div className={`${glass} p-6`}>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-zinc-800">Список голосов</h2>
          <button
            type="button"
            onClick={reload}
            className="text-sm text-zinc-700 hover:text-zinc-900"
          >
            Обновить
          </button>
        </div>
        {loading && <div className="mt-3 text-sm text-zinc-600">Загрузка…</div>}
        {!loading && (
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {sorted.map((v) => {
              const canDelete = !BUILTIN_IDS.has(v.id);
              const sampleUrl = getAppApiVoiceSampleUrl(v.id);
              return (
                <div key={v.id} className={`${glassCard} p-4 space-y-2`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold text-zinc-800">{v.name}</div>
                      <div className="text-xs text-zinc-600">id: {v.id} · role: {v.role}</div>
                    </div>
                    <button
                      type="button"
                      disabled={!canDelete}
                      onClick={() => handleDelete(v.id)}
                      className="text-xs text-red-600 hover:text-red-800 disabled:text-zinc-400"
                    >
                      Удалить
                    </button>
                  </div>
                  {sampleUrl && <audio controls className="w-full" src={sampleUrl} />}
                </div>
              );
            })}
            {sorted.length === 0 && !loading && (
              <div className="text-sm text-zinc-600">Голоса не найдены.</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

