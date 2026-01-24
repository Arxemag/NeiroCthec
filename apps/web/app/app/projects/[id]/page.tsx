'use client';

import { useEffect, useMemo, useState } from 'react';
import { apiJson } from '../../../../lib/api';
import { Button } from '../../../../components/ui';
import { useParams } from 'next/navigation';

type Voice = { id: string; name: string; language: string; gender: string; style: string };
type Project = {
  id: string;
  title: string;
  text: string;
  language: string;
  status: string;
  voices?: { voiceId: string; voice: Voice }[];
};
type AudioItem = { id: string; status: string; format?: string | null; durationSeconds?: number | null; createdAt: string };

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [selectedVoiceIds, setSelectedVoiceIds] = useState<string[]>([]);
  const [audios, setAudios] = useState<AudioItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);

  const streamSrc = useMemo(() => {
    const ready = audios.find((a) => a.status === 'ready');
    if (!ready) return null;
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:4000';
    return `${base}/api/audios/${ready.id}/stream`;
  }, [audios]);

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [p, v, a] = await Promise.all([
        apiJson<{ project: Project }>(`/api/projects/${projectId}`),
        apiJson<{ voices: Voice[] }>('/api/voices'),
        apiJson<{ audios: AudioItem[] }>(`/api/projects/${projectId}/audios`),
      ]);
      setProject(p.project);
      setVoices(v.voices);
      setAudios(a.audios);
      const initial = (p.project.voices ?? []).map((x) => x.voiceId);
      setSelectedVoiceIds(initial.length ? initial : v.voices.slice(0, 1).map((x) => x.id));
    } catch (e: any) {
      setError(e?.message ?? 'Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll();
  }, [projectId]);

  async function saveProject() {
    if (!project) return;
    setSaving(true);
    setError(null);
    try {
      const out = await apiJson<{ project: Project }>(`/api/projects/${projectId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          title: project.title,
          text: project.text,
          language: project.language,
          voiceIds: selectedVoiceIds,
        }),
      });
      setProject(out.project);
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось сохранить');
    } finally {
      setSaving(false);
    }
  }

  async function generateAudio() {
    setGenerating(true);
    setError(null);
    try {
      await saveProject();
      await apiJson(`/api/projects/${projectId}/generate-audio`, { method: 'POST' });
      // Poll list (MVP)
      await loadAll();
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось запустить генерацию');
    } finally {
      setGenerating(false);
    }
  }

  if (loading) return <div className="text-sm text-zinc-300">Загрузка…</div>;
  if (!project) return <div className="text-sm text-zinc-300">Проект не найден</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--color-accent)]">Проект</h1>
          <div className="mt-1 text-sm text-zinc-400">
            Статус: <span className="text-zinc-200">{project.status}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" disabled={saving} onClick={saveProject}>
            {saving ? 'Сохраняем…' : 'Сохранить'}
          </Button>
          <Button disabled={generating} onClick={generateAudio}>
            {generating ? 'Запускаем…' : 'Сгенерировать аудио'}
          </Button>
        </div>
      </div>

      {error && <div className="rounded-lg border border-red-900 bg-red-950/40 p-3 text-sm text-red-200">{error}</div>}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3">
          <label className="text-sm text-zinc-300">Название</label>
          <input
            className="w-full rounded-lg border border-zinc-800 bg-primary px-3 py-2 outline-none focus:border-indigo-500"
            value={project.title}
            onChange={(e) => setProject({ ...project, title: e.target.value })}
          />
          <label className="text-sm text-zinc-300">Язык</label>
          <input
            className="w-full rounded-lg border border-zinc-800 bg-primary px-3 py-2 outline-none focus:border-indigo-500"
            value={project.language}
            onChange={(e) => setProject({ ...project, language: e.target.value })}
          />
        </div>

        <div className="space-y-3">
          <div className="text-sm text-zinc-300">Голоса (можно несколько)</div>
          <div className="max-h-48 overflow-auto rounded-lg border border-zinc-800 bg-[var(--color-neutral-light)] p-2">
            {voices.map((v) => {
              const checked = selectedVoiceIds.includes(v.id);
              return (
                <label key={v.id} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 hover:bg-zinc-900">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => {
                      setSelectedVoiceIds((prev) =>
                        checked ? prev.filter((x) => x !== v.id) : [...prev, v.id],
                      );
                    }}
                  />
                  <div className="text-sm">
                    <div className="text-primary">{v.name}</div>
                    <div className="text-xs text-[var(--color-secondary)]">
                      {v.language} · {v.gender} · {v.style}
                    </div>
                  </div>
                </label>
              );
            })}
          </div>
          <div className="text-xs text-zinc-400">
            В MVP выбранные голоса сохраняются на проекте; распределение реплик по персонажам — следующий этап.
          </div>
        </div>
      </div>

      <div>
        <label className="text-sm text-zinc-300">Текст</label>
        <textarea
          className="mt-2 h-56 w-full rounded-lg border border-zinc-800 bg-[var(--color-neutral-light)] px-3 py-2 outline-none focus:border-indigo-500"
          value={project.text}
          onChange={(e) => setProject({ ...project, text: e.target.value })}
        />
      </div>

      <div className="rounded-2xl border border-zinc-800 bg-[var(--color-background)] p-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="font-medium text-[var(--color-accent)]">Результат</div>
            <div className="mt-1 text-sm text-primary">
              Плеер воспроизводит аудио через защищённый стриминг (без прямых ссылок на файл).
            </div>
          </div>
          <button onClick={loadAll} className="text-sm text-indigo-300 hover:text-indigo-200">
            Обновить
          </button>
        </div>

        <div className="mt-4">
          {streamSrc ? (
            // Browser will send Range requests automatically for seek.
            <audio controls className="w-full" src={streamSrc} />
          ) : (
            <div className="text-sm text-priamry">Пока нет готового аудио (или генерация в процессе).</div>
          )}
        </div>

        <div className="mt-4 space-y-2">
          {audios.map((a) => (
            <div key={a.id} className="rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-4">
                <div className="text-zinc-200">
                  {a.id.slice(0, 8)}… · {a.status}
                </div>
                <div className="text-xs text-zinc-500">{new Date(a.createdAt).toLocaleString()}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

