'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { apiJson } from '../../../lib/api';
import { Button } from '../../../components/ui';
import { useRouter } from 'next/navigation';

type Project = {
  id: string;
  title: string;
  language: string;
  status: string;
  updatedAt: string;
};

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiJson<{ projects: Project[] }>('/api/projects');
      setProjects(data.projects);
    } catch (e: any) {
      setError(e?.message ?? 'Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function createQuickProject() {
    try {
      const voices = await apiJson<{ voices: { id: string }[] }>('/api/voices');
      const firstVoiceId = voices.voices?.[0]?.id;
      if (!firstVoiceId) throw new Error('Нет доступных голосов');
      const out = await apiJson<{ project: { id: string } }>('/api/projects', {
        method: 'POST',
        body: JSON.stringify({
          title: 'Новый проект',
          language: 'ru-RU',
          text: 'Привет! Это тестовый проект НейроЧтец.',
          voiceIds: [firstVoiceId],
        }),
      });
      router.push(`/app/projects/${out.project.id}`);
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось создать проект');
    }
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--color-accent)]">Проекты</h1>
          <p className="mt-1 text-sm text-zinc-300">Создавайте проекты, выбирайте голоса и генерируйте аудио.</p>
        </div>
        <Button onClick={createQuickProject}>Создать проект</Button>
      </div>

      {error && <div className="mt-4 rounded-lg border border-red-900 bg-red-950/40 p-3 text-sm text-red-200">{error}</div>}

      <div className="mt-6">
        {loading ? (
          <div className="text-sm text-zinc-300">Загрузка…</div>
        ) : projects.length === 0 ? (
          <div className="rounded-2xl border border-zinc-800 bg-zinc-950/40 p-6 text-sm text-zinc-300">
            Пока нет проектов. Нажмите «Создать проект».
          </div>
        ) : (
          <div className="grid gap-3">
            {projects.map((p) => (
              <Link
                key={p.id}
                href={`/app/projects/${p.id}`}
                className="rounded-2xl border border-zinc-800 bg-zinc-950/40 p-4 hover:bg-zinc-950/60"
              >
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="font-medium text-[var(--color-accent)]">{p.title}</div>
                    <div className="mt-1 text-sm text-zinc-400">
                      {p.language} · {p.status}
                    </div>
                  </div>
                  <div className="text-xs text-zinc-500">{new Date(p.updatedAt).toLocaleString()}</div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      <div className="mt-6">
        <button onClick={load} className="text-sm text-indigo-300 hover:text-indigo-200">
          Обновить список
        </button>
      </div>
    </div>
  );
}

