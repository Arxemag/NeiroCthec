'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Check, Trash2, X } from 'lucide-react';
import { apiJson } from '../../../lib/api';
import { getAppApiUrl, deleteBooksByProject } from '../../../lib/app-api';
import { Button } from '../../../components/ui';
import { useRouter } from 'next/navigation';

type Project = {
  id: string;
  title: string;
  language: string;
  status: string;
  updatedAt: string;
};

type TrashedProject = {
  id: string;
  title: string;
  language: string;
  status: string;
  deletedAt: string;
};

export default function ProjectsPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [expandedDeleteId, setExpandedDeleteId] = useState<string | null>(null);
  const [showTrash, setShowTrash] = useState(false);
  const [trash, setTrash] = useState<TrashedProject[]>([]);
  const [trashLoading, setTrashLoading] = useState(false);
  const [restoringId, setRestoringId] = useState<string | null>(null);

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

  async function loadTrash() {
    setTrashLoading(true);
    setError(null);
    try {
      const data = await apiJson<{ projects: TrashedProject[] }>('/api/projects/trash');
      setTrash(data.projects);
    } catch (e: any) {
      setError(e?.message ?? 'Ошибка загрузки корзины');
    } finally {
      setTrashLoading(false);
    }
  }

  async function deleteProject(id: string, _title: string) {
    setExpandedDeleteId(null);
    setDeletingId(id);
    setError(null);
    try {
      if (getAppApiUrl()) {
        await deleteBooksByProject(id).catch(() => {});
      }
      await apiJson(`/api/projects/${id}`, { method: 'DELETE' });
      setProjects((prev) => prev.filter((p) => p.id !== id));
      if (showTrash) loadTrash();
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось удалить проект');
    } finally {
      setDeletingId(null);
    }
  }

  async function restoreProject(id: string) {
    setRestoringId(id);
    setError(null);
    try {
      const data = await apiJson<{ project: { id: string; title: string; language: string; status: string; updatedAt: string } }>(`/api/projects/${id}/restore`, { method: 'POST' });
      setTrash((prev) => prev.filter((p) => p.id !== id));
      setProjects((prev) => [data.project, ...prev]);
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось восстановить проект');
    } finally {
      setRestoringId(null);
    }
  }

  function formatTrashRemaining(deletedAt: string) {
    const hoursSince = (Date.now() - new Date(deletedAt).getTime()) / (60 * 60 * 1000);
    const remaining = Math.max(0, Math.ceil(72 - hoursSince));
    if (remaining >= 24) return `Осталось ~${Math.ceil(remaining / 24)} д`;
    return `Осталось ~${remaining} ч`;
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-text">Мои проекты</h1>
          <p className="mt-1 text-sm text-textSecondary">Создавайте проекты, выбирайте голоса и генерируйте аудио.</p>
        </div>
        <Button
          onClick={createQuickProject}
          className="!bg-[var(--color-accent)] !text-[var(--color-primary)] hover:!opacity-90"
        >
          Создать проект
        </Button>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      <div className="mt-6">
        {loading ? (
          <div className="text-sm text-textSecondary">Загрузка…</div>
        ) : projects.length === 0 ? (
          <div className="rounded-2xl border border-border bg-surfaceSoft p-6 text-sm text-textSecondary">
            Пока нет проектов. Нажмите «Создать проект».
          </div>
        ) : (
          <div className="grid gap-3">
            {projects.map((p) => (
              <div
                key={p.id}
                className="flex items-center gap-3 rounded-2xl border border-border bg-surfaceSoft p-4 transition-colors hover:bg-surface hover:border-accent/30"
              >
                <Link href={`/app/projects/${p.id}`} className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <div className="font-medium text-text">{p.title}</div>
                      <div className="mt-1 text-sm text-textSecondary">
                        {p.language} · {p.status}
                      </div>
                    </div>
                    <div className="shrink-0 text-xs text-textMuted">{new Date(p.updatedAt).toLocaleString()}</div>
                  </div>
                </Link>
                {expandedDeleteId === p.id ? (
                  <div className="flex shrink-0 items-center gap-1 rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-900/20 overflow-hidden">
                    <button
                      type="button"
                      onClick={() => deleteProject(p.id, p.title)}
                      disabled={deletingId === p.id}
                      className="flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 disabled:opacity-50"
                      aria-label="Подтвердить удаление"
                    >
                      <Check className="h-3.5 w-3.5" />
                      Подтвердить
                    </button>
                    <button
                      type="button"
                      onClick={() => setExpandedDeleteId(null)}
                      disabled={deletingId === p.id}
                      className="flex items-center gap-1 border-l border-red-300 dark:border-red-800 px-2 py-1.5 text-xs font-medium text-textSecondary hover:bg-surface disabled:opacity-50"
                      aria-label="Отменить удаление"
                    >
                      <X className="h-3.5 w-3.5" />
                      Отменить
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={() => setExpandedDeleteId(p.id)}
                    disabled={deletingId === p.id}
                    className="shrink-0 rounded p-2 text-textMuted hover:bg-red-900/20 hover:text-red-400 disabled:opacity-50 transition-colors"
                    aria-label="Удалить проект"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-4">
        <button onClick={load} className="text-sm text-primary dark:text-accent hover:text-text hover:underline transition-colors">
          Обновить список
        </button>
        <button
          type="button"
          onClick={() => {
            setShowTrash((v) => {
              if (!v) loadTrash();
              return !v;
            });
          }}
          className="flex items-center gap-1.5 text-sm text-textSecondary hover:text-text transition-colors"
        >
          <Trash2 className="h-4 w-4" />
          {showTrash ? 'Скрыть корзину' : 'Корзина'}
        </button>
      </div>

      {showTrash && (
        <div className="mt-6 rounded-2xl border border-border bg-surfaceSoft p-4">
          <div className="mb-2 text-sm font-medium text-text">Корзина</div>
          <p className="mb-3 text-xs text-textSecondary">
            Удалённые проекты хранятся 72 часа. Восстановите проект до истечения срока.
          </p>
          {trashLoading ? (
            <div className="py-4 text-sm text-textMuted">Загрузка…</div>
          ) : trash.length === 0 ? (
            <div className="py-4 text-center text-sm text-textMuted">В корзине пусто.</div>
          ) : (
            <ul className="space-y-2">
              {trash.map((p) => (
                <li
                  key={p.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 py-2"
                >
                  <div className="min-w-0">
                    <span className="font-medium text-text">{p.title}</span>
                    <span className="ml-2 text-xs text-textMuted">
                      {p.language} · {p.status} · {formatTrashRemaining(p.deletedAt)}
                    </span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => restoreProject(p.id)}
                    disabled={restoringId === p.id}
                  >
                    {restoringId === p.id ? 'Восстановление…' : 'Восстановить'}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

