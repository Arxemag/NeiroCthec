'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { apiJson } from '../../../lib/api';
import {
  getAppApiVoiceSampleUrl,
  getAudioSettings,
  isAppApiEnabled,
  listVoices,
  parseXtts2SettingsFromConfig,
  putXtts2Settings,
  uploadVoice,
  deleteVoice,
  type AppVoice,
  type Xtts2Settings,
} from '../../../lib/app-api';

type Metrics = {
  totalUsers: number;
  totalProjects: number;
  totalAudios: number;
  projectsByStatus: Record<string, number>;
  audiosByStatus: Record<string, number>;
  subscriptionByStatus: Record<string, number>;
  newUsersLast7Days: number;
  newUsersLast30Days: number;
  projectsCreatedLast7Days: number;
  audiosCreatedLast7Days: number;
};

const glass = 'rounded-2xl border border-zinc-300/50 bg-zinc-100/90 shadow-xl backdrop-blur-xl';
const glassCard = 'rounded-2xl border border-zinc-300/40 bg-zinc-100/80 backdrop-blur-lg';

const VOICES_BUILTIN_IDS = new Set(['narrator', 'male', 'female']);

export default function AdminPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [xtts2, setXtts2] = useState<Xtts2Settings>({
    temperature: 0.35,
    lengthPenalty: 1.0,
    repetitionPenalty: 2.0,
    topK: 50,
    topP: 0.85,
    speed: 1.0,
    language: 'ru',
    splitSentences: true,
  });
  const [xtts2Loading, setXtts2Loading] = useState(false);
  const [xtts2Saving, setXtts2Saving] = useState(false);
  const [xtts2Error, setXtts2Error] = useState<string | null>(null);
  const [xtts2Success, setXtts2Success] = useState(false);
  const appApiEnabled = isAppApiEnabled();

  const [voices, setVoices] = useState<AppVoice[]>([]);
  const [voicesLoading, setVoicesLoading] = useState(true);
  const [voicesError, setVoicesError] = useState<string | null>(null);
  const [voicesUploading, setVoicesUploading] = useState(false);
  const [voicesUploadError, setVoicesUploadError] = useState<string | null>(null);
  const [selectedVoiceFile, setSelectedVoiceFile] = useState<File | null>(null);

  const voicesSorted = useMemo(() => [...voices].sort((a, b) => a.name.localeCompare(b.name)), [voices]);

  const loadXtts2Settings = useCallback(async () => {
    if (!appApiEnabled) return;
    setXtts2Loading(true);
    setXtts2Error(null);
    try {
      const res = await getAudioSettings();
      setXtts2(parseXtts2SettingsFromConfig(res?.config));
    } catch (e) {
      setXtts2Error(e instanceof Error ? e.message : 'Не удалось загрузить настройки');
    } finally {
      setXtts2Loading(false);
    }
  }, [appApiEnabled]);

  useEffect(() => {
    loadXtts2Settings();
  }, [loadXtts2Settings]);

  const loadVoices = useCallback(async () => {
    if (!appApiEnabled) {
      setVoicesLoading(false);
      return;
    }
    setVoicesLoading(true);
    setVoicesError(null);
    try {
      const data = await listVoices();
      setVoices(data);
    } catch (e: unknown) {
      setVoicesError(e instanceof Error ? e.message : 'Ошибка загрузки голосов');
    } finally {
      setVoicesLoading(false);
    }
  }, [appApiEnabled]);

  useEffect(() => {
    loadVoices();
  }, [loadVoices]);

  const handleVoiceUpload = async () => {
    if (!selectedVoiceFile) return;
    setVoicesUploading(true);
    setVoicesUploadError(null);
    try {
      await uploadVoice(selectedVoiceFile);
      setSelectedVoiceFile(null);
      await loadVoices();
    } catch (e: unknown) {
      setVoicesUploadError(e instanceof Error ? e.message : 'Ошибка загрузки');
    } finally {
      setVoicesUploading(false);
    }
  };

  const handleVoiceDelete = async (id: string) => {
    if (!id || VOICES_BUILTIN_IDS.has(id)) return;
    try {
      await deleteVoice(id);
      await loadVoices();
    } catch (e: unknown) {
      setVoicesError(e instanceof Error ? e.message : 'Ошибка удаления');
    }
  };

  const saveXtts2Settings = async () => {
    if (!appApiEnabled) return;
    setXtts2Saving(true);
    setXtts2Error(null);
    setXtts2Success(false);
    try {
      await putXtts2Settings(xtts2);
      setXtts2Success(true);
      setTimeout(() => setXtts2Success(false), 3000);
    } catch (e) {
      setXtts2Error(e instanceof Error ? e.message : 'Не удалось сохранить');
    } finally {
      setXtts2Saving(false);
    }
  };

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiJson<Metrics>('/api/admin/metrics');
        setMetrics(data);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : 'Ошибка загрузки');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-text">Админ-панель</h1>
          <p className="mt-1 text-sm text-textSecondary">Метрики и управление пользователями</p>
        </div>
        <Link
          href="/app/admin/users"
          className="inline-flex items-center rounded-lg bg-zinc-800 px-4 py-2 font-medium text-zinc-50 hover:bg-zinc-700"
        >
          Пользователи
        </Link>
      </div>

      {/* Настройки XTTS2 — только при подключённом App API (Core) */}
      <div className={`${glass} p-6`}>
        <h2 className="text-lg font-semibold text-zinc-800">Настройки XTTS2</h2>
        <p className="mt-1 text-sm text-zinc-600">
          Управляйте «характером» XTTS2: креативность (температура), длина фраз, склонность к
          повторам, степень вариативности (top‑k/top‑p), скорость речи и язык. Эти параметры
          применяются ко всем новым озвучкам, где выбран движок «XTTS2».
        </p>
        {!appApiEnabled && (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            Подключите Core API (NEXT_PUBLIC_APP_API_URL), чтобы загружать и сохранять настройки XTTS2.
          </div>
        )}
        {appApiEnabled && (
          <>
            {xtts2Error && (
              <div className="mt-3 rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">
                {xtts2Error}
              </div>
            )}
            {xtts2Success && (
              <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                Настройки сохранены.
              </div>
            )}
            {xtts2Loading ? (
              <div className="mt-4 text-sm text-zinc-600">Загрузка настроек…</div>
            ) : (
              <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-700">Температура</label>
                  <input
                    type="number"
                    min={0.05}
                    max={2}
                    step={0.05}
                    value={xtts2.temperature ?? 0.35}
                    onChange={(e) =>
                      setXtts2((s) => ({ ...s, temperature: parseFloat(e.target.value) || 0.35 }))
                    }
                    className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-800 focus:border-[#7A6CFF] focus:outline-none focus:ring-1 focus:ring-[#7A6CFF]"
                  />
                  <p className="mt-1 text-xs text-zinc-500">
                    0.05–2, по умолчанию 0.35. Чем выше, тем более «живой» и вариативной будет
                    речь, но может появиться больше артефактов и непредсказуемости. Чем ниже —
                    тем спокойнее, ровнее и предсказуемее речь.
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700">Length penalty</label>
                  <input
                    type="number"
                    min={0.1}
                    max={5}
                    step={0.1}
                    value={xtts2.lengthPenalty ?? 1.0}
                    onChange={(e) =>
                      setXtts2((s) => ({ ...s, lengthPenalty: parseFloat(e.target.value) || 1.0 }))
                    }
                    className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-800 focus:border-[#7A6CFF] focus:outline-none focus:ring-1 focus:ring-[#7A6CFF]"
                  />
                  <p className="mt-1 text-xs text-zinc-500">
                    Штраф за длину (1.0 по умолчанию). Меньше 1.0 — модель будет чаще «обрубать»
                    фразы и говорить короче. Больше 1.0 — стремится проговаривать фразы до конца,
                    иногда чуть растягивая.
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700">Repetition penalty</label>
                  <input
                    type="number"
                    min={1}
                    max={5}
                    step={0.1}
                    value={xtts2.repetitionPenalty ?? 2.0}
                    onChange={(e) =>
                      setXtts2((s) => ({
                        ...s,
                        repetitionPenalty: parseFloat(e.target.value) || 2.0,
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-800 focus:border-[#7A6CFF] focus:outline-none focus:ring-1 focus:ring-[#7A6CFF]"
                  />
                  <p className="mt-1 text-xs text-zinc-500">
                    Штраф за повторы (2.0 по умолчанию). Увеличивайте, если слышите «залипания»,
                    растянутые звуки или зацикливания. Слишком низкие значения могут приводить к
                    монотонным повторам.
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700">Top‑k</label>
                  <input
                    type="number"
                    min={0}
                    max={200}
                    step={1}
                    value={xtts2.topK ?? 50}
                    onChange={(e) =>
                      setXtts2((s) => ({ ...s, topK: parseInt(e.target.value || '50', 10) }))
                    }
                    className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-800 focus:border-[#7A6CFF] focus:outline-none focus:ring-1 focus:ring-[#7A6CFF]"
                  />
                  <p className="mt-1 text-xs text-zinc-500">
                    Top‑k сэмплинг (50 по умолчанию). 0 — выключить (модель выбирает самые
                    вероятные варианты). Меньше 50 — речь более предсказуемая и «деловая»,
                    больше 50 — больше вариативности и неожиданных оборотов.
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700">Top‑p</label>
                  <input
                    type="number"
                    min={0.1}
                    max={1}
                    step={0.05}
                    value={xtts2.topP ?? 0.85}
                    onChange={(e) =>
                      setXtts2((s) => ({ ...s, topP: parseFloat(e.target.value) || 0.85 }))
                    }
                    className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-800 focus:border-[#7A6CFF] focus:outline-none focus:ring-1 focus:ring-[#7A6CFF]"
                  />
                  <p className="mt-1 text-xs text-zinc-500">
                    Top‑p (nucleus)‑сэмплинг (0.85 по умолчанию). Уменьшайте, если хотите максимально
                    стабильное чтение (0.7–0.8). Увеличивайте к 0.9–0.95 для более свободной и
                    артистичной манеры.
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700">Скорость</label>
                  <input
                    type="number"
                    min={0.5}
                    max={2}
                    step={0.05}
                    value={xtts2.speed ?? 1.0}
                    onChange={(e) =>
                      setXtts2((s) => ({ ...s, speed: parseFloat(e.target.value) || 1.0 }))
                    }
                    className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-800 focus:border-[#7A6CFF] focus:outline-none focus:ring-1 focus:ring-[#7A6CFF]"
                  />
                  <p className="mt-1 text-xs text-zinc-500">
                    0.5–2, по умолчанию 1.0. Значения ближе к 1.0 дают наиболее естественную речь.
                    0.8–0.9 — более медленное, вдумчивое чтение; 1.1–1.3 — чуть более энергичное.
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-zinc-700">Язык</label>
                  <select
                    value={xtts2.language ?? 'ru'}
                    onChange={(e) => setXtts2((s) => ({ ...s, language: e.target.value }))}
                    className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-zinc-800 focus:border-[#7A6CFF] focus:outline-none focus:ring-1 focus:ring-[#7A6CFF]"
                  >
                    <option value="ru">Русский</option>
                    <option value="en">English</option>
                    <option value="de">Deutsch</option>
                    <option value="es">Español</option>
                    <option value="fr">Français</option>
                    <option value="it">Italiano</option>
                    <option value="pl">Polski</option>
                    <option value="pt">Português</option>
                    <option value="tr">Türkçe</option>
                  </select>
                </div>
                <div className="sm:col-span-2 lg:col-span-1">
                  <label className="block text-sm font-medium text-zinc-700">
                    Делить текст на предложения
                  </label>
                  <div className="mt-2 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() =>
                        setXtts2((s) => ({ ...s, splitSentences: !s.splitSentences }))
                      }
                      className={`relative inline-flex h-6 w-11 items-center rounded-full border transition-colors ${
                        xtts2.splitSentences
                          ? 'border-emerald-500 bg-emerald-500'
                          : 'border-zinc-300 bg-zinc-200'
                      }`}
                    >
                      <span
                        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                          xtts2.splitSentences ? 'translate-x-5' : 'translate-x-1'
                        }`}
                      />
                    </button>
                  </div>
                  <p className="mt-2 text-xs text-zinc-600">
                    Включено (по умолчанию): длинный текст режется на предложения, что экономит
                    память и ускоряет генерацию, но может слегка ломать интонационные дуги между
                    фразами. Отключите, если важна максимально связная, «поточная» речь при
                    достаточном количестве ресурсов.
                  </p>
                </div>
              </div>
            )}
            {!xtts2Loading && (
              <div className="mt-4">
                <button
                  type="button"
                  onClick={saveXtts2Settings}
                  disabled={xtts2Saving}
                  className="rounded-lg bg-[#7A6CFF] px-4 py-2 font-medium text-white hover:bg-[#6A5CEF] disabled:opacity-50"
                >
                  {xtts2Saving ? 'Сохранение…' : 'Сохранить настройки XTTS2'}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {/* Голоса (загрузка и список) — при подключённом App API */}
      <div className={`${glass} p-6 space-y-4`}>
        <h2 className="text-lg font-semibold text-zinc-800">Голоса (voice samples)</h2>
        <p className="text-sm text-zinc-600">Управление голосами для TTS. Загрузка WAV до 30 секунд.</p>
        {!appApiEnabled && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            Подключите Core API (NEXT_PUBLIC_APP_API_URL), чтобы загружать и просматривать голоса.
          </div>
        )}
        {appApiEnabled && (
          <>
            <div className={`${glassCard} p-4 space-y-3`}>
              <h3 className="font-medium text-zinc-800">Загрузить новый голос</h3>
              <input
                type="file"
                accept=".wav,audio/wav"
                onChange={(e) => setSelectedVoiceFile(e.target.files?.[0] ?? null)}
              />
              <div className="flex gap-3">
                <button
                  type="button"
                  disabled={!selectedVoiceFile || voicesUploading}
                  onClick={handleVoiceUpload}
                  className="inline-flex items-center rounded-lg bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-50 hover:bg-zinc-700 disabled:opacity-50"
                >
                  {voicesUploading ? 'Загрузка…' : 'Загрузить'}
                </button>
                {voicesUploadError && <div className="text-sm text-red-700">{voicesUploadError}</div>}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-zinc-800">Список голосов</h3>
              <button type="button" onClick={loadVoices} className="text-sm text-zinc-700 hover:text-zinc-900">
                Обновить
              </button>
            </div>
            {voicesLoading && <div className="text-sm text-zinc-600">Загрузка…</div>}
            {!voicesLoading && (
              <div className="grid gap-4 md:grid-cols-2">
                {voicesSorted.map((v) => {
                  const canDelete = !VOICES_BUILTIN_IDS.has(v.id);
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
                          onClick={() => handleVoiceDelete(v.id)}
                          className="text-xs text-red-600 hover:text-red-800 disabled:text-zinc-400"
                        >
                          Удалить
                        </button>
                      </div>
                      {sampleUrl && <audio controls className="w-full" src={sampleUrl} />}
                    </div>
                  );
                })}
                {voicesSorted.length === 0 && (
                  <div className="text-sm text-zinc-600">Голоса не найдены.</div>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>
      )}

      {loading && <div className="text-sm text-zinc-600">Загрузка метрик…</div>}

      {metrics && !loading && (
        <div className={`${glass} p-6`}>
          <h2 className="text-lg font-semibold text-zinc-800">Метрики сервиса</h2>

          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className={`${glassCard} p-4`}>
              <div className="text-2xl font-bold text-[#7A6CFF]">{metrics.totalUsers}</div>
              <div className="text-sm text-zinc-600">Пользователей</div>
            </div>
            <div className={`${glassCard} p-4`}>
              <div className="text-2xl font-bold text-[#7A6CFF]">{metrics.totalProjects}</div>
              <div className="text-sm text-zinc-600">Проектов</div>
            </div>
            <div className={`${glassCard} p-4`}>
              <div className="text-2xl font-bold text-[#7A6CFF]">{metrics.totalAudios}</div>
              <div className="text-sm text-zinc-600">Аудио</div>
            </div>
            <div className={`${glassCard} p-4`}>
              <div className="text-2xl font-bold text-emerald-600">+{metrics.newUsersLast7Days}</div>
              <div className="text-sm text-zinc-600">Новых за 7 дней</div>
            </div>
          </div>

          <div className="mt-6 grid gap-6 md:grid-cols-2">
            <div className={`${glassCard} p-4`}>
              <h3 className="font-medium text-zinc-800">Проекты по статусу</h3>
              <ul className="mt-2 space-y-1 text-sm text-zinc-600">
                {Object.entries(metrics.projectsByStatus).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v}
                  </li>
                ))}
              </ul>
            </div>
            <div className={`${glassCard} p-4`}>
              <h3 className="font-medium text-zinc-800">Аудио по статусу</h3>
              <ul className="mt-2 space-y-1 text-sm text-zinc-600">
                {Object.entries(metrics.audiosByStatus).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-4">
            <div className={`${glassCard} p-4`}>
              <h3 className="font-medium text-zinc-800">Подписки по статусу</h3>
              <ul className="mt-2 space-y-1 text-sm text-zinc-600">
                {Object.entries(metrics.subscriptionByStatus).map(([k, v]) => (
                  <li key={k}>
                    {k}: {v}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="text-sm text-zinc-600">
              Новых пользователей за 30 дней: <strong className="text-zinc-800">{metrics.newUsersLast30Days}</strong>
            </div>
            <div className="text-sm text-zinc-600">
              Проектов создано за 7 дней: <strong className="text-zinc-800">{metrics.projectsCreatedLast7Days}</strong>
            </div>
            <div className="text-sm text-zinc-600">
              Аудио создано за 7 дней: <strong className="text-zinc-800">{metrics.audiosCreatedLast7Days}</strong>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
