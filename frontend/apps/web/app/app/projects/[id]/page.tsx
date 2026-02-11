'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, FileUp, History, Pencil, Trash2, X } from 'lucide-react';
import { apiJson, API_BASE } from '../../../../lib/api';
import { Button } from '../../../../components/ui';
import { useParams, useRouter } from 'next/navigation';

const TEXT_HISTORY_KEY = 'neurochtec_text_history';
const TEXT_HISTORY_MAX = 10;

type TextHistoryItem = { id: string; text: string; preview: string; addedAt: number; fileName?: string };

function getTextHistory(): TextHistoryItem[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(TEXT_HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function addToTextHistory(text: string, fileName?: string): void {
  if (typeof window === 'undefined') return;
  const arr = getTextHistory();
  const preview = text.slice(0, 60).replace(/\s+/g, ' ').trim() + (text.length > 60 ? '…' : '');
  arr.unshift({
    id: (typeof crypto !== 'undefined' && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now()),
    text,
    preview,
    addedAt: Date.now(),
    fileName,
  });
  localStorage.setItem(TEXT_HISTORY_KEY, JSON.stringify(arr.slice(0, TEXT_HISTORY_MAX)));
}

function removeFromTextHistory(id: string): void {
  if (typeof window === 'undefined') return;
  const arr = getTextHistory().filter((x) => x.id !== id);
  localStorage.setItem(TEXT_HISTORY_KEY, JSON.stringify(arr));
}

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
  const router = useRouter();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [selectedVoiceIds, setSelectedVoiceIds] = useState<string[]>([]);
  const [audios, setAudios] = useState<AudioItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [showTitleEdit, setShowTitleEdit] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [textHistory, setTextHistory] = useState<TextHistoryItem[]>([]);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const streamSrc = useMemo(() => {
    const ready = audios.find((a) => a.status === 'ready');
    if (!ready) return null;
    return `${API_BASE}/api/audios/${ready.id}/stream`;
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

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const fileName = file.name;
    const r = new FileReader();
    r.onload = () => {
      const text = String(r.result ?? '');
      if (project) setProject({ ...project, text });
      addToTextHistory(text, fileName);
      setTextHistory(getTextHistory());
    };
    r.readAsText(file, 'UTF-8');
    e.target.value = '';
  }

  function applyFromHistory(item: TextHistoryItem) {
    if (project) setProject({ ...project, text: item.text });
    setShowHistory(false);
  }

  function deleteFromHistory(id: string, e: React.MouseEvent) {
    e.stopPropagation();
    removeFromTextHistory(id);
    setTextHistory(getTextHistory());
  }

  async function deleteProject() {
    setShowDeleteConfirm(false);
    setDeleting(true);
    setError(null);
    try {
      await apiJson(`/api/projects/${projectId}`, { method: 'DELETE' });
      router.push('/app/projects');
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось удалить проект');
    } finally {
      setDeleting(false);
    }
  }

  if (loading) return <div className="text-sm text-zinc-600">Загрузка…</div>;
  if (!project) return <div className="text-sm text-zinc-600">Проект не найден</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold text-[var(--color-primary)]">{project.title}</h1>
            <button
              type="button"
              onClick={() => setShowTitleEdit((v) => !v)}
              className="rounded p-1 text-[var(--color-primary)] opacity-70 hover:bg-zinc-200/80 hover:opacity-100"
              aria-label="Изменить название"
            >
              <Pencil className="h-4 w-4" />
            </button>
          </div>
          <div className="mt-1 text-sm text-zinc-600">
            Статус: <span className="text-zinc-900">{project.status}</span>
          </div>
        </div>
        <Button variant="secondary" disabled={saving} onClick={saveProject}>
          {saving ? 'Сохраняем…' : 'Сохранить'}
        </Button>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>}

      {showTitleEdit && (
        <div className="space-y-3">
          <label className="text-sm text-zinc-700">Название</label>
          <input
            className="w-full rounded-lg border border-zinc-300/40 bg-zinc-200/90 px-3 py-2 text-zinc-900 outline-none focus:border-[#7A6CFF]"
            value={project.title}
            onChange={(e) => setProject({ ...project, title: e.target.value })}
          />
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <label className="text-sm text-zinc-700">Текст</label>
            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".txt,.text,text/plain"
                className="hidden"
                onChange={handleFileSelect}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                className="gap-1.5"
              >
                <FileUp className="h-3.5 w-3.5" />
                Загрузить из файла
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowHistory((v) => !v);
                  if (!showHistory) setTextHistory(getTextHistory());
                }}
                className="gap-1.5"
              >
                <History className="h-3.5 w-3.5" />
                Ранее загруженные
              </Button>
            </div>
          </div>
          <textarea
            className="mt-2 h-56 w-full resize-y rounded-lg border border-zinc-300/40 bg-zinc-200/90 px-3 py-2 text-zinc-900 outline-none focus:border-[#7A6CFF]"
            value={project.text}
            onChange={(e) => setProject({ ...project, text: e.target.value })}
          />
          {showHistory && (
            <div className="mt-3 rounded-lg border border-zinc-300/40 bg-zinc-100/80 p-2">
              <div className="mb-2 text-xs font-medium text-[var(--color-primary)]">Ранее загруженные тексты</div>
              {textHistory.length === 0 ? (
                <div className="py-4 text-center text-sm text-zinc-500">Нет сохранённых текстов. Загрузите .txt файл — он попадёт сюда.</div>
              ) : (
                <ul className="max-h-40 space-y-1 overflow-auto">
                  {textHistory.map((item) => (
                    <li
                      key={item.id}
                      onClick={() => applyFromHistory(item)}
                      className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-left hover:bg-zinc-200/60"
                    >
                      <span className="min-w-0 flex-1 truncate text-sm text-[var(--color-primary)]" title={item.preview}>
                        {item.fileName ?? item.preview}
                      </span>
                      <span className="shrink-0 text-xs text-zinc-500">
                        {new Date(item.addedAt).toLocaleDateString()}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => deleteFromHistory(item.id, e)}
                        className="shrink-0 rounded p-1 text-zinc-400 hover:bg-zinc-300/60 hover:text-red-600"
                        aria-label="Удалить из истории"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>

        <div className="space-y-3">
          <div className="text-base font-medium text-[var(--color-primary)]">Используемые голоса персонажей в данном проекте</div>
          <div className="max-h-48 overflow-auto rounded-lg border border-zinc-300/40 bg-zinc-100/80 p-2">
            {voices.map((v) => {
              const checked = selectedVoiceIds.includes(v.id);
              return (
                <label key={v.id} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 hover:bg-zinc-200/50">
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
                    <div className="font-medium text-[var(--color-primary)]">{v.name}</div>
                    <div className="text-xs text-[var(--color-primary)] opacity-90">
                      {v.language} · {v.gender} · {v.style}
                    </div>
                  </div>
                </label>
              );
            })}
          </div>
          <div className="text-xs text-[var(--color-primary)] opacity-80">
            В MVP выбранные голоса сохраняются на проекте; распределение реплик по персонажам — следующий этап.
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-start gap-4">
        <div className="shrink-0">
          <Button disabled={generating} onClick={generateAudio}>
            {generating ? 'Запускаем…' : 'Сгенерировать озвучку'}
          </Button>
        </div>
        <div className="min-w-0 flex-1 rounded-2xl border border-zinc-300/40 bg-zinc-100/80 p-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="font-medium text-[#7A6CFF]">Результат</div>
            <div className="mt-1 text-sm text-zinc-700">
              Плеер воспроизводит аудио через защищённый стриминг (без прямых ссылок на файл).
            </div>
          </div>
          <button onClick={loadAll} className="text-sm text-[#7A6CFF] hover:underline">
            Обновить
          </button>
        </div>

        <div className="mt-4">
          {streamSrc ? (
            <audio controls className="w-full" src={streamSrc} />
          ) : (
            <div className="text-sm text-zinc-600">Пока нет готового аудио (или генерация в процессе).</div>
          )}
        </div>

        <div className="mt-4 space-y-2">
          {audios.map((a) => (
            <div key={a.id} className="rounded-lg border border-zinc-300/30 bg-zinc-100/70 px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-4">
                <div className="text-zinc-700">
                  {a.id.slice(0, 8)}… · {a.status}
                </div>
                <div className="text-xs text-zinc-500">{new Date(a.createdAt).toLocaleString()}</div>
              </div>
            </div>
          ))}
        </div>
        </div>
      </div>

      <div className="flex justify-end">
        {showDeleteConfirm ? (
          <div className="flex items-center gap-1 rounded-lg border border-red-200 bg-red-50/80 overflow-hidden">
            <button
              type="button"
              onClick={deleteProject}
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
            aria-label="Удалить проект"
          >
            Удалить проект
          </button>
        )}
      </div>
    </div>
  );
}

