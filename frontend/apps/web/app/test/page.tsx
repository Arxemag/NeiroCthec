'use client';

import { useEffect, useMemo, useState } from 'react';
import { API_BASE, apiJson } from '../../lib/api';
import { Button, Container } from '../../components/ui';

type DemoChapter = {
  id: string;
  title: string;
  textLength: number;
  status: 'pending' | 'processing' | 'ready' | 'error';
  durationSeconds: number | null;
};

type DemoTask = {
  id: string;
  fileName: string;
  stage: 0 | 1 | 2 | 3 | 4 | 5;
  stageLabel: string;
  stageStartedAt: number;
  voiceRequested: boolean;
  chapters: DemoChapter[];
};

const stages = [
  'Stage 0 · Книга загружена',
  'Stage 1 · Извлечение текста',
  'Stage 2 · Нормализация',
  'Stage 3 · Разбивка на главы',
  'Stage 4 · Контейнер озвучки',
  'Stage 5 · Готовые главы',
];

export default function DemoBookPage() {
  const [task, setTask] = useState<DemoTask | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!task || task.stage >= 5) return;
    const timer = setInterval(async () => {
      try {
        const out = await apiJson<{ task: DemoTask }>(`/api/demo/tasks/${task.id}`);
        setTask(out.task);
      } catch {
        // silent poll fail
      }
    }, 1300);
    return () => clearInterval(timer);
  }, [task?.id, task?.stage]);

  const readyCount = useMemo(
    () => (task?.chapters ?? []).filter((c) => c.status === 'ready').length,
    [task?.chapters],
  );

  async function onUpload(file: File) {
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      const out = await apiJson<{ task: DemoTask }>('/api/demo/upload', {
        method: 'POST',
        body: form,
      });
      setTask(out.task);
    } catch (e: any) {
      setError(e?.message ?? 'Ошибка загрузки книги');
    } finally {
      setLoading(false);
    }
  }

  async function startVoice() {
    if (!task) return;
    setLoading(true);
    setError(null);
    try {
      const out = await apiJson<{ task: DemoTask }>(`/api/demo/tasks/${task.id}/start-voice`, {
        method: 'POST',
      });
      setTask(out.task);
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось отправить на озвучку');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 px-4 py-10 text-zinc-100">
      <Container>
        <div className="mx-auto w-full max-w-5xl space-y-6">
          <div className="rounded-2xl border border-zinc-700 bg-zinc-900/90 p-6">
            <h1 className="text-2xl font-semibold">Тест озвучки книги (без регистрации)</h1>
            <p className="mt-2 text-sm text-zinc-400">
              Загружаете файл, бэкенд проходит stage 0-3, затем отправляете stage 4 в контейнер озвучки и получаете stage 5 с готовыми главами.
            </p>

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <label className="cursor-pointer rounded-lg border border-zinc-600 bg-zinc-800 px-4 py-2 text-sm hover:bg-zinc-700">
                Загрузить книгу (.txt)
                <input
                  type="file"
                  accept=".txt,text/plain"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) void onUpload(file);
                    e.currentTarget.value = '';
                  }}
                />
              </label>

              <Button disabled={!task || task.stage < 3 || task.stage >= 4 || loading} onClick={() => void startVoice()}>
                Отправить на озвучку
              </Button>

              {task && <div className="text-xs text-zinc-400">Файл: {task.fileName}</div>}
            </div>

            {error && <div className="mt-4 rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-300">{error}</div>}
          </div>

          <div className="rounded-2xl border border-zinc-700 bg-zinc-900/90 p-6">
            <div className="text-sm font-medium">Статус пайплайна</div>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {stages.map((label, index) => {
                const active = task?.stage === index;
                const done = (task?.stage ?? -1) > index;
                return (
                  <div
                    key={label}
                    className={`rounded-lg border px-3 py-2 text-sm ${done ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-300' : active ? 'border-indigo-500/50 bg-indigo-500/10 text-indigo-300' : 'border-zinc-700 text-zinc-400'}`}
                  >
                    {label}
                  </div>
                );
              })}
            </div>
            <div className="mt-4 text-xs text-zinc-500">{task?.stageLabel ?? 'Ожидаем загрузку книги'}</div>
          </div>

          <div className="rounded-2xl border border-zinc-700 bg-zinc-900/90 p-6">
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium">Озвученные главы</div>
              <div className="text-xs text-zinc-400">Готово: {readyCount}/{task?.chapters.length ?? 0}</div>
            </div>

            {!task?.chapters.length && <div className="mt-4 text-sm text-zinc-500">Главы появятся после stage 3.</div>}

            <div className="mt-4 space-y-3">
              {task?.chapters.map((chapter) => (
                <div key={chapter.id} className="rounded-xl border border-zinc-700 bg-zinc-800/60 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-medium">{chapter.title}</div>
                      <div className="text-xs text-zinc-400">Символов: {chapter.textLength}</div>
                    </div>
                    <div className="text-xs text-zinc-400">{chapter.status}</div>
                  </div>
                  {chapter.status === 'ready' ? (
                    <audio
                      controls
                      className="mt-3 w-full"
                      src={`${API_BASE}/api/demo/tasks/${task.id}/chapters/${chapter.id}/stream`}
                    />
                  ) : (
                    <div className="mt-3 text-xs text-zinc-500">Аудио будет доступно после завершения stage 5.</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </Container>
    </main>
  );
}
