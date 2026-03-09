'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, FileUp, Pause, Pencil, Play, Trash2, X } from 'lucide-react';
import { apiJson, API_BASE } from '../../../../lib/api';
import { getAccessToken, getStoredUserId } from '../../../../lib/auth';
import { isAppApiEnabled, getAppApiUrl, getAppApiVoiceSampleUrl, getBookChapterAudioUrl, listVoices, listBooksByProject, appFetch, appJson, putAudioConfigVoiceIds, processBookStage4, getPreviewBySpeakers, getBookStatus, downloadBookAudio, deleteBook, deleteBooksByProject, uploadVoice, deleteVoice, type AppBook, type TtsEngine, type SpeakerSettings } from '../../../../lib/app-api';
import { Button } from '../../../../components/ui';
import { useParams, useRouter } from 'next/navigation';
import { cacheProjectFile, getCachedFile, createFileFromCache, hasCachedFile } from '../../../../lib/file-cache';
import { ProjectProgressSidebar } from '../../../../components/project-progress-sidebar';


type Voice = { 
  id: string; 
  name: string; 
  role: 'narrator' | 'actor';
  language: string; 
  gender: string; 
  style: string;
  hasSample?: boolean;
};
type Project = {
  id: string;
  title: string;
  text?: string;
  language: string;
  status: string;
  voices?: { voiceId: string; voice: Voice }[];
  voiceSettings?: { narratorVoiceId?: string | null; maleVoiceId?: string | null; femaleVoiceId?: string | null } | null;
};
type AudioItem = { id: string; status: string; format?: string | null; durationSeconds?: number | null; createdAt: string };
/** Формат ответа бэка GET /api/projects/:id/chapters (План 1). Поддержка snake_case из API. */
type Chapter = {
  id: string;
  title: string;
  order?: number;
  audioId?: string;
  durationSeconds?: number;
  createdAt: string;
};

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const projectId = params.id;

  const [project, setProject] = useState<Project | null>(null);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [selectedVoiceIds, setSelectedVoiceIds] = useState<{
    narrator?: string;
    male?: string;
    female?: string;
  }>({});
  const [audios, setAudios] = useState<AudioItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [showTitleEdit, setShowTitleEdit] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [completing, setCompleting] = useState(false);
  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const [processingProgress, setProcessingProgress] = useState<number>(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [hasStartedGeneration, setHasStartedGeneration] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ id: string; file: File; name: string; bookId?: string }>>([]);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const audioRefs = useRef<Record<string, HTMLAudioElement | null>>({});
  const progressIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [previewAudios, setPreviewAudios] = useState<AudioItem[]>([]);
  const [isFullProcessing, setIsFullProcessing] = useState(false);
  const [fullProcessingStatus, setFullProcessingStatus] = useState<'idle' | 'processing' | 'queued' | 'ready' | 'error'>('idle');
  const [fullProcessingProgress, setFullProcessingProgress] = useState<number>(0);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [chaptersError, setChaptersError] = useState<string | null>(null);
  const [showCreateBookConfirm, setShowCreateBookConfirm] = useState(false);
  const [creatingBook, setCreatingBook] = useState(false);
  const [hasListenedToFinalAudio, setHasListenedToFinalAudio] = useState(false);
  const fullProcessingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadInProgress, setUploadInProgress] = useState(false);
  const uploadErrorTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  /** ID книги в App, полученный при загрузке файла (POST /books/upload). Используется для запуска озвучки и прогресс-бара. */
  const [lastUploadedBookId, setLastUploadedBookId] = useState<string | null>(null);
  /** Blob URL финального аудио книги (GET /books/{id}/download), показывается в «Предпрослушать результат». */
  const [finalBookAudioUrl, setFinalBookAudioUrl] = useState<string | null>(null);
  /** Движок TTS: qwen3 или xtts2 (сохраняется в /books/settings/audio). */
  const [ttsEngine, setTtsEngine] = useState<TtsEngine>('qwen3');
  const finalBookAudioUrlRef = useRef<string | null>(null);
  /** Список книг проекта из App API (загруженные текстовые файлы). */
  const [projectBooks, setProjectBooks] = useState<AppBook[]>([]);
  /** Номера готовых глав (из GET /books/:id/status chapters_ready) — для раннего воспроизведения по главам. */
  const [chaptersReadyFromApp, setChaptersReadyFromApp] = useState<number[]>([]);
  /** Превью по спикерам: URL аудио для narrator, male, female (после «Озвучить фрагмент»). */
  const [previewFragmentUrls, setPreviewFragmentUrls] = useState<{ narrator?: string; male?: string; female?: string } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  /** Настройки скорости и тембра по спикерам. Вариант A: одна пара для всех (дефолт). */
  const [speakerSettings, setSpeakerSettings] = useState<SpeakerSettings>({
    narrator: { tempo: 1.0, pitch: 0 },
    male: { tempo: 1.0, pitch: 0 },
    female: { tempo: 1.0, pitch: 0 },
  });
  /** Принудительно переозвучить все строки (игнорировать готовые wav) — иначе в stage4 не уйдёт, если всё уже «готово». */
  const [forceReSynthesize, setForceReSynthesize] = useState(false);
  /** Свои голоса: форма загрузки и удаление */
  const [showAddVoiceForm, setShowAddVoiceForm] = useState(false);
  const [voiceUploadFile, setVoiceUploadFile] = useState<File | null>(null);
  const [voiceUploadName, setVoiceUploadName] = useState('');
  const [voiceUploadRole, setVoiceUploadRole] = useState<'narrator' | 'male' | 'female' | ''>('');
  const [voiceUploading, setVoiceUploading] = useState(false);
  const [voiceUploadError, setVoiceUploadError] = useState<string | null>(null);
  const [deletingVoiceId, setDeletingVoiceId] = useState<string | null>(null);
  const voiceFileInputRef = useRef<HTMLInputElement>(null);

  /** Нормализует главу из ответа бэка (snake_case → camelCase). */
  function normalizeChapter(raw: Record<string, unknown>): Chapter {
    return {
      id: String(raw.id ?? ''),
      title: String(raw.title ?? ''),
      order: typeof raw.order === 'number' ? raw.order : undefined,
      audioId: typeof raw.audio_id === 'string' ? raw.audio_id : typeof raw.audioId === 'string' ? raw.audioId : undefined,
      durationSeconds: typeof raw.duration_seconds === 'number' ? raw.duration_seconds : typeof raw.durationSeconds === 'number' ? raw.durationSeconds : undefined,
      createdAt: typeof raw.created_at === 'string' ? raw.created_at : typeof raw.createdAt === 'string' ? raw.createdAt : new Date().toISOString(),
    };
  }

  async function loadChapters() {
    setChaptersError(null);
    try {
      const data = await apiJson<{ chapters: unknown[] }>(`/api/projects/${projectId}/chapters`);
      const list = Array.isArray(data.chapters) ? data.chapters : [];
      setChapters(list.map((c) => normalizeChapter(typeof c === 'object' && c !== null ? (c as Record<string, unknown>) : {})));
    } catch (e: any) {
      console.warn('Не удалось загрузить главы:', e);
      setChapters([]);
      setChaptersError('Главы недоступны');
    }
  }

  async function checkFullProcessingStatus() {
    try {
      // Используем существующий endpoint проекта для проверки статуса
      const data = await apiJson<{ project: Project }>(`/api/projects/${projectId}`);
      const projectStatus = data.project.status;
      
      setFullProcessingStatus(projectStatus as 'processing' | 'queued' | 'ready' | 'error');
      
      // Обновляем проект в состоянии
      setProject(data.project);
      
      // Симулируем прогресс на основе статуса (можно будет заменить на реальный прогресс из API)
      if (projectStatus === 'queued') {
        setFullProcessingProgress(10);
      } else if (projectStatus === 'processing') {
        // Увеличиваем прогресс постепенно, если статус processing
        setFullProcessingProgress((prev) => Math.min(prev + 5, 90));
      }
      
      if (projectStatus === 'ready') {
        setIsFullProcessing(false);
        setFullProcessingProgress(100);
        if (fullProcessingIntervalRef.current) {
          clearInterval(fullProcessingIntervalRef.current);
          fullProcessingIntervalRef.current = null;
        }
        // Загружаем главы после завершения обработки
        await loadChapters();
      } else if (projectStatus === 'error') {
        setIsFullProcessing(false);
        if (fullProcessingIntervalRef.current) {
          clearInterval(fullProcessingIntervalRef.current);
          fullProcessingIntervalRef.current = null;
        }
        setError('Ошибка при полной обработке книги');
      }
    } catch (e: any) {
      console.error('Ошибка проверки статуса обработки:', e);
      // Если ошибка, останавливаем отслеживание
      setIsFullProcessing(false);
      if (fullProcessingIntervalRef.current) {
        clearInterval(fullProcessingIntervalRef.current);
        fullProcessingIntervalRef.current = null;
      }
    }
  }

  function startFullProcessingTracking() {
    if (fullProcessingIntervalRef.current) {
      clearInterval(fullProcessingIntervalRef.current);
    }
    
    // Проверяем статус сразу
    checkFullProcessingStatus();
    
    // Затем проверяем каждые 2 секунды
    fullProcessingIntervalRef.current = setInterval(() => {
      checkFullProcessingStatus();
    }, 2000);
  }

  async function loadAll(opts?: { silent?: boolean }) {
    if (!opts?.silent) {
      setLoading(true);
    }
    setError(null);
    try {
      const mapAppVoicesToVoice = (appVoices: { id: string; name: string; role: string }[]) =>
        appVoices.map((av) => ({
          id: av.id,
          name: av.name,
          role: (av.role === 'narrator' ? 'narrator' : 'actor') as 'narrator' | 'actor',
          language: 'ru',
          gender: av.role === 'male' ? 'male' : av.role === 'female' ? 'female' : 'neutral',
          style: '',
          hasSample: true,
        }));

      const loadVoices = (async (): Promise<Voice[]> => {
        const appUrl = getAppApiUrl();
        if (appUrl) {
          try {
            const appVoices = await listVoices();
            if (appVoices.length > 0) {
              // #region agent log
              try {
                fetch('http://127.0.0.1:7653/ingest/197dff00-57dd-45ca-809c-c08d9512ccf4', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '9376b5' }, body: JSON.stringify({ sessionId: '9376b5', hypothesisId: 'voices-fe', location: 'projects/[id]/page:loadVoices', message: 'Voices from Core', data: { source: 'app', count: appVoices.length }, timestamp: Date.now() }) }).catch(() => {});
              } catch (_) {}
              // #endregion
              return mapAppVoicesToVoice(appVoices);
            }
          } catch (e) {
            console.warn('[Voices] FastAPI /voices failed, falling back to Nest:', e);
          }
        }
        try {
          const r = await apiJson<{ voices?: Voice[] }>('/api/voices');
          const list = (r.voices ?? []) as Voice[];
          // #region agent log
          try {
            fetch('http://127.0.0.1:7653/ingest/197dff00-57dd-45ca-809c-c08d9512ccf4', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '9376b5' }, body: JSON.stringify({ sessionId: '9376b5', hypothesisId: 'voices-fe', location: 'projects/[id]/page:loadVoices', message: 'Voices from Nest', data: { source: 'nest', count: list.length }, timestamp: Date.now() }) }).catch(() => {});
          } catch (_) {}
          // #endregion
          return list;
        } catch (e) {
          // #region agent log
          try {
            fetch('http://127.0.0.1:7653/ingest/197dff00-57dd-45ca-809c-c08d9512ccf4', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '9376b5' }, body: JSON.stringify({ sessionId: '9376b5', hypothesisId: 'voices-fe', location: 'projects/[id]/page:loadVoices', message: 'Voices failed', data: { error: String(e) }, timestamp: Date.now() }) }).catch(() => {});
          } catch (_) {}
          // #endregion
          return [];
        }
      })();

      const [p, voicesList, a] = await Promise.all([
        apiJson<{ project: Project }>(`/api/projects/${projectId}`),
        loadVoices,
        apiJson<{ audios: AudioItem[] }>(`/api/projects/${projectId}/audios`),
      ]);

      let projectData = p.project;

      setProject(projectData);
      setVoices(voicesList as Voice[]);
      setAudios(a.audios);
      
      // Проверяем, находится ли проект в процессе полной обработки
      if (projectData.status === 'processing' || projectData.status === 'queued') {
        setIsFullProcessing(true);
        setFullProcessingStatus(projectData.status === 'processing' ? 'processing' : 'queued');
        // Начинаем отслеживание статуса полной обработки
        startFullProcessingTracking();
      } else if (projectData.status === 'ready') {
        // Если проект готов, проверяем наличие глав
        await loadChapters();
      }
      
      // Разделяем аудио на предварительные фрагменты и финальные
      // Предварительные фрагменты - это аудио со статусом 'ready' (все готовые фрагменты для предпрослушивания)
      let previewAudiosList = a.audios.filter((audio) => audio.status === 'ready');
      
      // Заглушка для тестирования проекта cmltq0vo80001p1p0180h5qhu
      if (projectId === 'cmltq0vo80001p1p0180h5qhu' && previewAudiosList.length === 0) {
        previewAudiosList = [
          {
            id: 'mock-audio-1',
            status: 'ready',
            format: 'mp3',
            durationSeconds: 120,
            createdAt: new Date().toISOString(),
          },
          {
            id: 'mock-audio-2',
            status: 'ready',
            format: 'mp3',
            durationSeconds: 95,
            createdAt: new Date(Date.now() - 60000).toISOString(),
          },
        ];
      }
      
      setPreviewAudios(previewAudiosList);

      // Если App API включён — подтягиваем уже загруженные книги проекта (только при валидном projectId)
      if (isAppApiEnabled() && projectId) {
        try {
          const books = await listBooksByProject(projectId);
          const list = Array.isArray(books) ? books : [];
          setProjectBooks(list);
          if (list.length > 0) setLastUploadedBookId(list[list.length - 1].id);
          // Загружаем финальный WAV, если есть готовое аудио
          const bookWithAudio = list.find((b) => b.final_audio_path);
          if (bookWithAudio) {
            try {
              const { blob } = await downloadBookAudio(bookWithAudio.id);
              if (finalBookAudioUrlRef.current) URL.revokeObjectURL(finalBookAudioUrlRef.current);
              const url = URL.createObjectURL(blob);
              finalBookAudioUrlRef.current = url;
              setFinalBookAudioUrl(url);
            } catch {
              /* аудио ещё не готово или недоступно */
            }
          }
        } catch (e) {
          console.warn('[App API] listBooksByProject failed:', e);
        }
        // Загружаем настройки аудио (в т.ч. tts_engine)
        try {
          const audioSettings = await appJson<{ config?: { tts_engine?: string } }>('/books/settings/audio').catch(() => ({}));
          const config = audioSettings && typeof audioSettings === 'object' && 'config' in audioSettings ? audioSettings.config : undefined;
          const engine = config?.tts_engine;
          if (engine === 'xtts2' || engine === 'qwen3') setTtsEngine(engine);
        } catch {
          /* ignore */
        }
      } else {
        setProjectBooks([]);
      }
      
      // Определяем, была ли начата генерация (если есть предварительные аудио или проект в обработке)
      if (previewAudiosList.length > 0 || p.project.status === 'processing' || p.project.status === 'queued') {
        setHasStartedGeneration(true);
      }
      
      // Обновляем прогресс на основе статуса проекта
      if (p.project.status === 'processing' || p.project.status === 'queued') {
        setIsProcessing(true);
        if (!progressIntervalRef.current) {
          startProgressTracking();
        }
      } else if (p.project.status === 'ready' || p.project.status === 'error') {
        setIsProcessing(false);
        setProcessingProgress(p.project.status === 'ready' ? 100 : 0);
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
          progressIntervalRef.current = null;
        }
        // Обновляем список аудио после завершения обработки
        const audiosData = await apiJson<{ audios: AudioItem[] }>(`/api/projects/${projectId}/audios`);
        let previewAudiosList = audiosData.audios.filter((audio) => audio.status === 'ready');
        
        // Заглушка для тестирования проекта cmltq0vo80001p1p0180h5qhu
        if (projectId === 'cmltq0vo80001p1p0180h5qhu' && previewAudiosList.length === 0) {
          previewAudiosList = [
            {
              id: 'mock-audio-1',
              status: 'ready',
              format: 'mp3',
              durationSeconds: 120,
              createdAt: new Date().toISOString(),
            },
            {
              id: 'mock-audio-2',
              status: 'ready',
              format: 'mp3',
              durationSeconds: 95,
              createdAt: new Date(Date.now() - 60000).toISOString(),
            },
          ];
        }
        
        setPreviewAudios(previewAudiosList);
      }
      
      // Инициализируем выбранные голоса по ролям.
      // Сохраняем уже выбранные пользователем голоса и подставляем дефолты только для пустых ролей.
      const initialVoices: { narrator?: string; male?: string; female?: string } = {
        ...selectedVoiceIds,
      };
      const projectVoices = p.project.voices ?? [];
      const vs = p.project.voiceSettings;

      if (projectVoices.length > 0) {
        for (const pv of projectVoices) {
          const voice = voicesList.find((vo) => vo.id === pv.voiceId);
          if (voice) {
            if (voice.role === 'narrator' && !initialVoices.narrator) initialVoices.narrator = voice.id;
            else if (voice.gender === 'male' && !initialVoices.male) initialVoices.male = voice.id;
            else if (voice.gender === 'female' && !initialVoices.female) initialVoices.female = voice.id;
          }
        }
      } else if (vs && (vs.narratorVoiceId || vs.maleVoiceId || vs.femaleVoiceId)) {
        if (vs.narratorVoiceId && !initialVoices.narrator) initialVoices.narrator = vs.narratorVoiceId;
        if (vs.maleVoiceId && !initialVoices.male) initialVoices.male = vs.maleVoiceId;
        if (vs.femaleVoiceId && !initialVoices.female) initialVoices.female = vs.femaleVoiceId;
      } else {
        if (isAppApiEnabled()) {
          if (voicesList.length > 0) {
            if (!initialVoices.narrator) initialVoices.narrator = voicesList[0].id;
            if (!initialVoices.male) initialVoices.male = voicesList.find((v) => v.gender === 'male')?.id ?? voicesList[0]?.id;
            if (!initialVoices.female) initialVoices.female = voicesList.find((v) => v.gender === 'female')?.id ?? voicesList[0]?.id;
          }
        } else {
          const narrator = voicesList.find((vo) => vo.role === 'narrator');
          const male = voicesList.find((vo) => vo.role === 'actor' && vo.gender === 'male');
          const female = voicesList.find((vo) => vo.role === 'actor' && vo.gender === 'female');
          if (narrator && !initialVoices.narrator) initialVoices.narrator = narrator.id;
          if (male && !initialVoices.male) initialVoices.male = male.id;
          if (female && !initialVoices.female) initialVoices.female = female.id;
        }
      }

      // При "тихих" обновлениях (после загрузки файла) не перезаписываем выбор пользователя,
      // если он уже что-то выбрал.
      const hadSelection = !!(selectedVoiceIds.narrator || selectedVoiceIds.male || selectedVoiceIds.female);
      if (!opts?.silent || !hadSelection) {
        setSelectedVoiceIds(initialVoices);
      }
    } catch (e: any) {
      setError(e?.message ?? 'Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  }

  /** Обновить только список голосов (после загрузки/удаления своего голоса). */
  async function refetchVoices() {
    const mapAppVoicesToVoice = (appVoices: { id: string; name: string; role: string }[]) =>
      appVoices.map((av) => ({
        id: av.id,
        name: av.name,
        role: (av.role === 'narrator' ? 'narrator' : 'actor') as 'narrator' | 'actor',
        language: 'ru',
        gender: av.role === 'male' ? 'male' : av.role === 'female' ? 'female' : 'neutral',
        style: '',
        hasSample: true,
      }));
    const appUrl = getAppApiUrl();
    if (appUrl) {
      try {
        const appVoices = await listVoices();
        if (appVoices.length > 0) {
          setVoices(mapAppVoicesToVoice(appVoices));
          return;
        }
      } catch (e) {
        console.warn('[Voices] refetchVoices: FastAPI /voices failed, falling back to Nest:', e);
      }
    }
    try {
      const r = await apiJson<{ voices?: Voice[] }>('/api/voices');
      setVoices((r.voices ?? []) as Voice[]);
    } catch {
      setVoices([]);
    }
  }

  async function handleUploadVoice() {
    if (!voiceUploadFile) {
      setVoiceUploadError('Выберите WAV-файл');
      return;
    }
    setVoiceUploadError(null);
    setVoiceUploading(true);
    try {
      await uploadVoice(voiceUploadFile, {
        name: voiceUploadName.trim() || undefined,
        role: voiceUploadRole || undefined,
      });
      setVoiceUploadFile(null);
      setVoiceUploadName('');
      setVoiceUploadRole('');
      setShowAddVoiceForm(false);
      if (voiceFileInputRef.current) voiceFileInputRef.current.value = '';
      await refetchVoices();
    } catch (e: any) {
      setVoiceUploadError(e?.message ?? 'Не удалось загрузить голос');
    } finally {
      setVoiceUploading(false);
    }
  }

  async function handleDeleteVoice(voiceId: string) {
    setDeletingVoiceId(voiceId);
    try {
      await deleteVoice(voiceId);
      setSelectedVoiceIds((prev) => {
        const next = { ...prev };
        if (prev.narrator === voiceId) next.narrator = undefined;
        if (prev.male === voiceId) next.male = undefined;
        if (prev.female === voiceId) next.female = undefined;
        return next;
      });
      await refetchVoices();
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось удалить голос');
    } finally {
      setDeletingVoiceId(null);
    }
  }

  useEffect(() => {
    void loadAll();
    
    // Проверяем наличие файла в кэше при загрузке страницы
    const cachedFile = getCachedFile(projectId);
    if (cachedFile && uploadedFiles.length === 0) {
      const file = createFileFromCache(cachedFile);
      setUploadedFiles([{ id: Date.now().toString(), file, name: cachedFile.fileName }]);
    }
  }, [projectId]);

  // Cleanup аудио элементов при размонтировании
  useEffect(() => {
    return () => {
      Object.values(audioRefs.current).forEach((audio) => {
        if (audio) {
          audio.pause();
          audio.src = '';
        }
      });
      audioRefs.current = {};
      
      // Cleanup интервалов
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
      if (fullProcessingIntervalRef.current) {
        clearInterval(fullProcessingIntervalRef.current);
      }
      if (uploadErrorTimeoutRef.current) {
        clearTimeout(uploadErrorTimeoutRef.current);
      }
      if (finalBookAudioUrlRef.current) {
        URL.revokeObjectURL(finalBookAudioUrlRef.current);
        finalBookAudioUrlRef.current = null;
      }
    };
  }, []);

  async function saveProject() {
    if (!project) return;
    setSaving(true);
    setError(null);
    try {
      const out = await apiJson<{ project: Project }>(`/api/projects/${projectId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          title: project.title,
          language: project.language,
          voiceIds: [
            ...(selectedVoiceIds.narrator ? [selectedVoiceIds.narrator] : []),
            ...(selectedVoiceIds.male ? [selectedVoiceIds.male] : []),
            ...(selectedVoiceIds.female ? [selectedVoiceIds.female] : []),
          ],
        }),
      });
      setProject(out.project);
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось сохранить');
    } finally {
      setSaving(false);
    }
  }

  async function saveTitle() {
    if (!project) return;
    setSaving(true);
    setError(null);
    try {
      const out = await apiJson<{ project: Project }>(`/api/projects/${projectId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: project.title }),
      });
      setProject(out.project);
      setShowTitleEdit(false);
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось сохранить название');
    } finally {
      setSaving(false);
    }
  }

  function startAppProgressTracking(bookId: string) {
    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    progressIntervalRef.current = setInterval(async () => {
      try {
        const st = await getBookStatus(bookId);
        setProcessingProgress(st.progress);
        if (Array.isArray(st.chapters_ready)) setChaptersReadyFromApp(st.chapters_ready);
        const isFinished = st.stage === 'completed' || st.stage === 'done' || st.stage === 'error' || st.progress >= 100;
        if (isFinished) {
          if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current);
            progressIntervalRef.current = null;
          }
          setIsProcessing(false);
          setProcessingProgress(st.stage === 'error' ? 0 : 100);
          if (st.stage === 'completed' || st.stage === 'done') {
            try {
              const { blob } = await downloadBookAudio(bookId);
              if (finalBookAudioUrlRef.current) URL.revokeObjectURL(finalBookAudioUrlRef.current);
              const url = URL.createObjectURL(blob);
              finalBookAudioUrlRef.current = url;
              setFinalBookAudioUrl(url);
            } catch {
              // 404/409 или сеть — аудио пока недоступно, не блокируем UI
            }
          }
        }
      } catch {
        if (progressIntervalRef.current) {
          clearInterval(progressIntervalRef.current);
          progressIntervalRef.current = null;
        }
        setIsProcessing(false);
      }
    }, 2000);
  }

  const activeBookId = lastUploadedBookId ?? projectBooks[0]?.id ?? null;

  async function fetchPreviewFragments() {
    if (!isAppApiEnabled()) return;
    if (!activeBookId) {
      setPreviewError('Сначала загрузите книгу');
      setPreviewFragmentUrls(null);
      return;
    }
    setPreviewError(null);
    setPreviewLoading(true);
    try {
      const urls = await getPreviewBySpeakers(activeBookId, selectedVoiceIds, speakerSettings);
      setPreviewFragmentUrls(urls);
    } catch (e: any) {
      setPreviewError(e?.message ?? 'Не удалось загрузить превью');
      setPreviewFragmentUrls(null);
    } finally {
      setPreviewLoading(false);
    }
  }

  async function reFetchPreviewFragments() {
    if (!isAppApiEnabled()) return;
    if (!activeBookId) {
      setPreviewError('Сначала загрузите книгу');
      setPreviewFragmentUrls(null);
      return;
    }
    setPreviewError(null);
    setPreviewLoading(true);
    try {
      const urls = await getPreviewBySpeakers(activeBookId, selectedVoiceIds, speakerSettings);
      setPreviewFragmentUrls(urls);
    } catch (e: any) {
      setPreviewError(e?.message ?? 'Не удалось переозвучить превью');
    } finally {
      setPreviewLoading(false);
    }
  }

  function updateSpeakerSettingsTempoPitch(tempo: number, pitch: number) {
    setSpeakerSettings((prev) => ({
      narrator: { ...prev.narrator, tempo, pitch },
      male: { ...prev.male, tempo, pitch },
      female: { ...prev.female, tempo, pitch },
    }));
  }

  async function generateAudio() {
    const appBookId = lastUploadedBookId ?? projectBooks[0]?.id ?? null;
    const hasFiles = uploadedFiles.length > 0 || (isAppApiEnabled() && appBookId);
    if (!hasFiles) {
      setError('Сначала загрузите файлы проекта');
      return;
    }

    setGenerating(true);
    setHasStartedGeneration(true);
    setError(null);
    setIsProcessing(true);
    setProcessingProgress(0);

    const appApiUrl = process.env.NEXT_PUBLIC_APP_API_URL ?? '';
    if (appApiUrl && appBookId) {
      if (finalBookAudioUrlRef.current) {
        URL.revokeObjectURL(finalBookAudioUrlRef.current);
        finalBookAudioUrlRef.current = null;
      }
      setFinalBookAudioUrl(null);
      setChaptersReadyFromApp([]);
      try {
        await putAudioConfigVoiceIds(selectedVoiceIds, { ttsEngine });
        const stage4Res = await processBookStage4(appBookId, 500, selectedVoiceIds, ttsEngine, speakerSettings, forceReSynthesize);
        if (stage4Res.remaining_tasks === 0 && stage4Res.all_lines_done) {
          setError(
            'Все строки уже озвучены. Включите «Принудительно переозвучить» или смените движок TTS/голоса и нажмите «Сгенерировать озвучку» снова.'
          );
        }
        startAppProgressTracking(appBookId);
      } catch (e: any) {
        const msg = e?.message ?? '';
        const isNetworkError = /failed to fetch|network error|load failed/i.test(msg) || msg === '';
        setError(
          isNetworkError
            ? `Нет связи с App API (порт 8000). Проверьте: сервер запущен, NEXT_PUBLIC_APP_API_URL=http://localhost:8000, CORS разрешён. Ошибка: ${msg || 'Failed to fetch'}`
            : msg || 'Не удалось запустить озвучку'
        );
        setIsProcessing(false);
        setProcessingProgress(0);
      } finally {
        setGenerating(false);
      }
      return;
    }

    try {
      await saveProject();
      await apiJson(`/api/projects/${projectId}/generate-audio`, { method: 'POST' });
      startProgressTracking();
      await loadAll();
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось запустить генерацию');
      setIsProcessing(false);
      setProcessingProgress(0);
    } finally {
      setGenerating(false);
    }
  }

  async function generateFullAudiobook() {
    if (!project) return;
    
    setCompleting(true);
    setIsFullProcessing(true);
    setFullProcessingStatus('queued');
    setFullProcessingProgress(0);
    setError(null);
    try {
      await apiJson(`/api/projects/${projectId}/complete`, { method: 'POST' });
      // Обновляем проект в состоянии (status может стать queued/processing)
      await loadAll({ silent: true });
      startFullProcessingTracking();
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось отправить книгу на полную обработку');
      setIsFullProcessing(false);
      setFullProcessingStatus('error');
      // Страницу не ломаем — только сообщение пользователю
    } finally {
      setCompleting(false);
    }
  }

  async function createBook() {
    if (!project) return;

    const appBookId = lastUploadedBookId ?? projectBooks.find((b) => b.final_audio_path)?.id;
    if (!appBookId) {
      setError('Нет озвученной книги для создания. Дождитесь завершения озвучки.');
      return;
    }

    setCreatingBook(true);
    setError(null);
    try {
      const appUserId = getStoredUserId() ?? (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_DEV_USER_ID) ?? undefined;
      await apiJson<{ bookId: string }>(`/api/projects/${projectId}/create-book`, {
        method: 'POST',
        body: JSON.stringify({ appBookId, ...(appUserId && { appUserId }) }),
      });
      router.push('/app/books');
    } catch (e: any) {
      console.error('Ошибка создания книги:', e);
      setError(e?.message ?? 'Не удалось создать аудио книгу. Endpoint может быть не реализован.');
      setShowCreateBookConfirm(false);
    } finally {
      setCreatingBook(false);
    }
  }

  const ALLOWED_BOOK_EXTENSIONS = ['.txt', '.fb2', '.epub', '.mobi'];
  function validateFileFormat(file: File): boolean {
    const fileName = file.name.toLowerCase();
    return ALLOWED_BOOK_EXTENSIONS.some((ext) => fileName.endsWith(ext));
  }

  function addFiles(files: FileList | File[]) {
    const fileArray = Array.from(files);
    const invalidFiles: string[] = [];
    const validFiles: Array<{ id: string; file: File; name: string }> = [];

    fileArray.forEach((file) => {
      if (!validateFileFormat(file)) {
        invalidFiles.push(file.name);
      } else {
        validFiles.push({
          id: `${Date.now()}-${Math.random()}`,
          file,
          name: file.name,
        });
      }
    });

    if (invalidFiles.length > 0) {
      setError(`Неподдерживаемые форматы файлов: ${invalidFiles.join(', ')}. Поддерживаются: ${ALLOWED_BOOK_EXTENSIONS.join(', ')}`);
    }

    if (validFiles.length > 0) {
      setUploadedFiles((prev) => [...prev, ...validFiles]);
      setError(null);
      setUploadSuccess(false);
    }
  }

  async function removeFile(fileId: string) {
    const file = uploadedFiles.find((f) => f.id === fileId);
    if (file?.bookId && getAppApiUrl()) {
      try {
        await deleteBook(file.bookId);
        setProjectBooks((prev) => prev.filter((b) => b.id !== file.bookId));
        if (finalBookAudioUrlRef.current) {
          URL.revokeObjectURL(finalBookAudioUrlRef.current);
          finalBookAudioUrlRef.current = null;
        }
        setFinalBookAudioUrl(null);
      } catch {
        // игнорируем ошибку удаления на сервере, файл убираем из списка
      }
    }
    setUploadedFiles((prev) => prev.filter((f) => f.id !== fileId));
    setLastUploadedBookId((prev) => (file?.bookId === prev ? null : prev));
    setUploadSuccess(false);
  }

  async function removeProjectBook(bookId: string) {
    if (!getAppApiUrl()) return;
    try {
      await deleteBook(bookId);
      setProjectBooks((prev) => prev.filter((b) => b.id !== bookId));
      setLastUploadedBookId((prev) => (prev === bookId ? null : prev));
      if (finalBookAudioUrlRef.current) {
        URL.revokeObjectURL(finalBookAudioUrlRef.current);
        finalBookAudioUrlRef.current = null;
      }
      setFinalBookAudioUrl(null);
      setUploadSuccess(false);
    } catch {
      setError('Не удалось удалить файл');
    }
  }

  async function processFiles() {
    if (uploadedFiles.length === 0) {
      setError('Нет файлов для загрузки');
      return;
    }

    setError(null);
    setUploadError(null);
    setUploadSuccess(false);
    setUploadInProgress(true);
    if (uploadErrorTimeoutRef.current) {
      clearTimeout(uploadErrorTimeoutRef.current);
      uploadErrorTimeoutRef.current = null;
    }

    try {
      if (isAppApiEnabled()) {
        const bookIds: string[] = [];
        const rawUserId = getStoredUserId() ?? (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_DEV_USER_ID) ?? 'anonymous';
        const userId = typeof rawUserId === 'string' ? rawUserId : 'anonymous';
        // Прокси загрузки: POST /upload-book (корень; /api/* уходит в Nest по rewrite)
        const uploadUrl =
          typeof window !== 'undefined'
            ? new URL('/upload-book', window.location.origin).href
            : '/upload-book';
        for (const fileData of uploadedFiles) {
          const formData = new FormData();
          formData.append('file', fileData.file);
          if (project?.title?.trim()) formData.append('project_title', project.title.trim());
          const response = await fetch(uploadUrl, {
            method: 'POST',
            headers: {
              'X-User-Id': userId,
              'X-Project-Id': projectId,
            },
            body: formData,
            credentials: 'include',
          });

          const text = await response.text();
          // #region agent log
          try {
            fetch('http://127.0.0.1:7653/ingest/197dff00-57dd-45ca-809c-c08d9512ccf4', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '9376b5' }, body: JSON.stringify({ sessionId: '9376b5', hypothesisId: 'upload-fe', location: 'projects/[id]/page:upload', message: 'Upload response', data: { uploadUrl, status: response.status, ok: response.ok, bodyPreview: text?.slice(0, 300) }, timestamp: Date.now() }) }).catch(() => {});
          } catch (_) {}
          // #endregion
          let msg = 'Загрузка не удалась, повторите попытку';

          if (response.status === 422) {
            try {
              const j = JSON.parse(text) as { detail?: string };
              if (typeof j?.detail === 'string') msg = j.detail;
            } catch {}
            setUploadError(msg);
            uploadErrorTimeoutRef.current = setTimeout(() => setUploadError(null), 15000);
            setUploadInProgress(false);
            return;
          }

          if (!response.ok) {
            try {
              const j = JSON.parse(text) as { detail?: string };
              if (typeof j?.detail === 'string') msg = j.detail;
              else if (response.status === 502) msg = j?.detail ?? 'Core API недоступен. Запустите сервис core (порт 8000) или проверьте APP_API_PROXY_TARGET в Docker.';
            } catch {}
            setUploadError(msg);
            uploadErrorTimeoutRef.current = setTimeout(() => setUploadError(null), 15000);
            setUploadInProgress(false);
            return;
          }

          let data: { id?: string; status?: string } = {};
          try {
            data = text ? JSON.parse(text) : {};
          } catch {}
          if (typeof data?.id === 'string') bookIds.push(data.id);
        }
        setUploadedFiles((prev) => prev.map((f, i) => ({ ...f, bookId: bookIds[i] ?? f.bookId })));
        if (bookIds.length > 0) setLastUploadedBookId(bookIds[bookIds.length - 1]);
        setUploadSuccess(true);
        setUploadedFiles([]);
        setUploadInProgress(false);
        // Обновляем список книг в фоне; не показываем ошибку, если бек уже принял книгу (GET /books 200)
        try {
          await loadAll({ silent: true });
        } catch (e) {
          console.warn('[Upload] Refresh after upload failed (book already saved):', e);
        }
        return;
      }

      // Fallback: загрузка в Nest API (проекты)
      for (const fileData of uploadedFiles) {
        await cacheProjectFile(projectId, fileData.file);
      }

      const base = API_BASE;
      const token = getAccessToken();

      for (const fileData of uploadedFiles) {
        const formData = new FormData();
        formData.append('file', fileData.file);

        const response = await fetch(`${base}/api/projects/${projectId}/upload-text`, {
          method: 'POST',
          headers: token ? { 'Authorization': `Bearer ${token}` } : {},
          body: formData,
          credentials: 'include',
        });

        if (!response.ok) {
          const text = await response.text();
          let msg = text || 'Не удалось загрузить файл';
          try {
            const j = JSON.parse(text);
            if (typeof (j as { message?: string }).message === 'string') msg = (j as { message: string }).message;
            else if (typeof (j as { error?: string }).error === 'string') msg = (j as { error: string }).error;
          } catch {
            /* оставляем msg как text */
          }
          throw new Error(msg);
        }
      }

      setUploadSuccess(true);
      setUploadError(null);
      await loadAll({ silent: true });
    } catch (e: any) {
      const errMsg = e?.message ?? 'Не удалось загрузить файлы';
      setError(errMsg);
      setUploadError(errMsg);
      uploadErrorTimeoutRef.current = setTimeout(() => {
        setUploadError(null);
        uploadErrorTimeoutRef.current = null;
      }, 15000);
    } finally {
      setUploadInProgress(false);
    }
  }

  async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    addFiles(files);
    e.target.value = '';
  }

  function openFileDialog() {
    if (!canUploadFile) return;
    fileInputRef.current?.click();
  }

  function handleDragEnter(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragging(true);
    }
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = 'copy';
    if (e.dataTransfer.types.includes('Files')) {
      setIsDragging(true);
    }
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragging(false);
    }
  }

  async function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    const files = e.dataTransfer.files;
    if (!files || files.length === 0) {
      setError('Не удалось получить файлы из перетаскивания');
      return;
    }
    
    addFiles(files);
  }

  function startProgressTracking() {
    // Очищаем предыдущий интервал если есть
    if (progressIntervalRef.current) {
      clearInterval(progressIntervalRef.current);
    }

    let currentProgress = processingProgress || 20;
    progressIntervalRef.current = setInterval(async () => {
      try {
        // Проверяем статус проекта
        const projectData = await apiJson<{ project: Project }>(`/api/projects/${projectId}`);
        const status = projectData.project.status;

        // Обновляем прогресс на основе статуса
        if (status === 'draft') {
          currentProgress = Math.max(currentProgress, 10);
        } else if (status === 'queued') {
          currentProgress = Math.max(currentProgress, 20);
        } else if (status === 'processing') {
          // Плавно увеличиваем прогресс от текущего значения до 90
          currentProgress = Math.min(currentProgress + 2, 90);
        } else if (status === 'ready') {
          currentProgress = 100;
          setIsProcessing(false);
          if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current);
            progressIntervalRef.current = null;
          }
        } else if (status === 'error') {
          setIsProcessing(false);
          setProcessingProgress(0);
          if (progressIntervalRef.current) {
            clearInterval(progressIntervalRef.current);
            progressIntervalRef.current = null;
          }
          return;
        }

        setProcessingProgress(currentProgress);
      } catch (e) {
        console.error('Failed to check project status:', e);
      }
    }, 1000); // Проверяем каждую секунду
  }

  useEffect(() => {
    // Очистка интервала при размонтировании
    return () => {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
      }
    };
  }, []);


  async function deleteProject() {
    setShowDeleteConfirm(false);
    setDeleting(true);
    setError(null);
    try {
      if (getAppApiUrl()) {
        await deleteBooksByProject(projectId).catch(() => {});
      }
      await apiJson(`/api/projects/${projectId}`, { method: 'DELETE' });
      router.push('/app/projects');
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось удалить проект');
    } finally {
      setDeleting(false);
    }
  }

  // Группируем голоса по ролям: Диктор, Мужской голос, Женский голос (данные приходят от FastAPI с полем role).
  const voicesByRole = useMemo(() => {
    const narrator = voices.filter((v) => v.role === 'narrator' || v.gender === 'neutral');
    const male = voices.filter((v) => v.gender === 'male');
    const female = voices.filter((v) => v.gender === 'female');
    return { narrator, male, female };
  }, [voices]);

  /** Свои (пользовательские) голоса: не встроенные narrator/male/female. Для блока «Свои голоса» и кнопки Удалить. */
  const customVoices = useMemo(
    () => voices.filter((v) => !['narrator', 'male', 'female'].includes(v.id)),
    [voices]
  );

  function getVoiceSampleUrl(voiceId: string): string | null {
    if (isAppApiEnabled()) {
      const url = getAppApiVoiceSampleUrl(voiceId);
      return url || null;
    }
    const base = API_BASE;
    return `${base}/api/voices/${voiceId}/sample`;
  }

  function getVoiceFileUrl(voice: Voice): string | null {
    if (voice.hasSample) return getVoiceSampleUrl(voice.id);
    return null;
  }

  async function handlePlayVoice(voice: Voice) {
    Object.values(audioRefs.current).forEach((audio) => {
      if (audio && audio !== audioRefs.current[voice.id]) {
        audio.pause();
        audio.currentTime = 0;
      }
    });

    if (playingVoiceId === voice.id) {
      const audio = audioRefs.current[voice.id];
      if (audio) {
        audio.pause();
        audio.currentTime = 0;
      }
      setPlayingVoiceId(null);
      return;
    }

    if (isAppApiEnabled()) {
      try {
        const res = await appFetch(`/voices/${encodeURIComponent(voice.id)}/sample`);
        if (!res.ok) throw new Error('Sample not found');
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        const audio = new Audio(blobUrl);
        audioRefs.current[voice.id] = audio;
        const revoke = () => {
          URL.revokeObjectURL(blobUrl);
          setPlayingVoiceId(null);
          delete audioRefs.current[voice.id];
        };
        audio.onended = revoke;
        audio.onerror = () => {
          console.error('Failed to play voice sample:', voice.id);
          revoke();
        };
        await audio.play();
        setPlayingVoiceId(voice.id);
      } catch (e) {
        console.error('Failed to load voice sample:', e);
      }
      return;
    }

    const audioUrl = getVoiceFileUrl(voice) || getVoiceSampleUrl(voice.id);
    if (!audioUrl) {
      console.warn('No audio URL available for voice:', voice.id);
      return;
    }

    let audio = audioRefs.current[voice.id];
    if (audio) {
      const needsRecreate = audio.src !== audioUrl || audio.error !== null || audio.ended;
      if (needsRecreate) {
        try {
          audio.pause();
          audio.src = '';
          audio.onended = null;
          audio.onerror = null;
        } catch {}
        audio = null;
        delete audioRefs.current[voice.id];
      } else {
        audio.currentTime = 0;
      }
    }

    if (!audio) {
      try {
        audio = new Audio(audioUrl);
        audioRefs.current[voice.id] = audio;
        audio.onended = () => setPlayingVoiceId(null);
        audio.onerror = () => {
          setPlayingVoiceId(null);
          try {
            if (audio) {
              audio.pause();
              audio.src = '';
              delete audioRefs.current[voice.id];
            }
          } catch {}
        };
      } catch (e) {
        console.error('Failed to create audio element:', e);
        setPlayingVoiceId(null);
        return;
      }
    }

    if (audio) {
      audio.play().then(() => setPlayingVoiceId(voice.id)).catch(() => setPlayingVoiceId(null));
    }
  }

  function handleSelectVoice(role: 'narrator' | 'male' | 'female', voiceId: string) {
    setSelectedVoiceIds((prev) => ({
      ...prev,
      [role]: prev[role] === voiceId ? undefined : voiceId,
    }));
  }

  const isCompleted = project?.status === 'completed';
  const canEdit = !isCompleted && project?.status !== 'processing';
  // Зона загрузки файла активна, если проект не завершен и не в процессе генерации
  // Если проект еще не загружен (null) или в статусе draft/ready, разрешаем загрузку
  const canUploadFile = !isCompleted && (project === null || (project.status !== 'processing' && project.status !== 'queued'));

  // Определяем шаги прогресса
  const progressSteps = useMemo(() => {
    const hasVoices = selectedVoiceIds.narrator || selectedVoiceIds.male || selectedVoiceIds.female;
    const hasFiles = uploadedFiles.length > 0 || (isAppApiEnabled() && lastUploadedBookId);
    const hasPreviewAudios = previewAudios.length > 0 || (isAppApiEnabled() && finalBookAudioUrl);
    const isFullyCompleted = isCompleted;
    const isGenerating = project?.status === 'processing' || project?.status === 'queued';
    const isReady = project?.status === 'ready';

    const step1Completed = hasVoices && hasFiles;
    const step2Completed = hasStartedGeneration || isGenerating || isReady;
    const step3Completed = hasPreviewAudios;
    const step4Completed = isFullyCompleted;

    // Определяем активный шаг (первый незавершенный)
    let activeStepId = 1;
    if (step1Completed && !step2Completed) activeStepId = 2;
    else if (step2Completed && !step3Completed) activeStepId = 3;
    else if (step3Completed && !step4Completed) activeStepId = 4;

    return [
      {
        id: 1,
        title: 'Выберите Голоса и Загрузите текст',
        completed: Boolean(step1Completed),
        active: activeStepId === 1,
      },
      {
        id: 2,
        title: 'Отправьте на предварительную озвучку',
        completed: Boolean(step2Completed),
        active: activeStepId === 2,
      },
      {
        id: 3,
        title: 'Прослушайте получившийся предварительный результат',
        completed: Boolean(step3Completed),
        active: activeStepId === 3,
      },
      {
        id: 4,
        title: 'Создайте итоговую аудио-книгу',
        completed: Boolean(step4Completed),
        active: activeStepId === 4,
      },
    ];
  }, [selectedVoiceIds, uploadedFiles.length, previewAudios.length, hasStartedGeneration, project?.status, isCompleted, lastUploadedBookId, finalBookAudioUrl]);
  
  async function completeProject() {
    if (!project || project.status !== 'ready') {
      setError('Можно завершить только готовые проекты');
      return;
    }

    setCompleting(true);
    setError(null);
    try {
      await apiJson(`/api/projects/${projectId}/complete`, { method: 'POST' });
      await loadAll();
      // Показываем сообщение об успехе, но не редиректим автоматически
      // Пользователь может остаться на странице или перейти в "Мои книги" сам
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось завершить проект');
    } finally {
      setCompleting(false);
    }
  }

  if (loading) return <div className="text-sm text-textSecondary">Загрузка…</div>;
  if (!project) return <div className="text-sm text-textSecondary">Проект не найден</div>;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
      <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-heading text-2xl font-semibold text-text">{project.title}</h1>
            {!isCompleted && (
              <button
                type="button"
                onClick={() => setShowTitleEdit((v) => !v)}
                className="rounded p-1 text-textSecondary opacity-70 hover:bg-surfaceSoft hover:opacity-100 transition-colors"
                aria-label="Изменить название"
              >
                <Pencil className="h-4 w-4" />
              </button>
            )}
          </div>
          <div className="mt-1 text-sm text-textSecondary">
            Статус: <span className="text-text">{project.status}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isCompleted && (
            <div className="rounded-lg bg-green-100/80 px-4 py-2 text-sm font-medium text-green-800">
              ✓ Проект завершен
            </div>
          )}
        </div>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-100/80 p-3 text-sm text-red-800">{error}</div>}

      {showTitleEdit && !isCompleted && (
        <div className="space-y-3">
          <label className="text-sm text-text">Название</label>
          <div className="flex items-center gap-2">
            <input
              className="flex-1 min-w-0 rounded-lg border border-border bg-surface px-3 py-2 text-text outline-none focus:border-accent focus:ring-2 focus:ring-accent/20 transition-colors"
              value={project.title}
              onChange={(e) => setProject({ ...project, title: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void saveTitle();
                }
                if (e.key === 'Escape') {
                  setShowTitleEdit(false);
                  void loadAll({ silent: true });
                }
              }}
              disabled={!canEdit}
              autoFocus
            />
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={() => void saveTitle()}
              disabled={!canEdit || saving}
              title="Сохранить название"
              className="shrink-0"
            >
              <Check className="h-4 w-4" />
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setShowTitleEdit(false);
                void loadAll({ silent: true });
              }}
              disabled={saving}
              title="Отмена"
              className="shrink-0"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {isCompleted && (
        <div className="rounded-lg border border-green-300/40 bg-green-50/80 p-4">
          <div className="flex items-center gap-2">
            <div className="text-lg">✓</div>
            <div>
              <div className="font-medium text-green-800">Проект завершен</div>
              <div className="text-sm text-green-700">
                Этот проект завершен и недоступен для редактирования. Готовая аудиокнига доступна в разделе "Мои книги".
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Движок TTS: Qwen3 или XTTS2 */}
      {!isCompleted && isAppApiEnabled() && (
        <div className="space-y-2">
          <div className="text-base font-medium text-text">Движок TTS</div>
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="tts_engine"
                checked={ttsEngine === 'qwen3'}
                onChange={() => {
                  setTtsEngine('qwen3');
                  putAudioConfigVoiceIds(selectedVoiceIds, { ttsEngine: 'qwen3' }).catch(() => {});
                }}
                className="cursor-pointer"
              />
              <span className="text-sm text-text">Qwen3</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="tts_engine"
                checked={ttsEngine === 'xtts2'}
                onChange={() => {
                  setTtsEngine('xtts2');
                  putAudioConfigVoiceIds(selectedVoiceIds, { ttsEngine: 'xtts2' }).catch(() => {});
                }}
                className="cursor-pointer"
              />
              <span className="text-sm text-text">XTTS2</span>
            </label>
          </div>
        </div>
      )}

      {/* Свои голоса: загрузка и список (только на странице проекта, только при включённом App API) */}
      {!isCompleted && isAppApiEnabled() && (
        <div className="space-y-3 rounded-2xl border border-border bg-surfaceSoft p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <div className="text-base font-medium text-text">Свои голоса</div>
              <div className="text-xs text-textSecondary">
                Загрузите WAV-файл для использования в ролях диктора, мужского или женского голоса.
              </div>
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => {
                setShowAddVoiceForm((v) => !v);
                setVoiceUploadError(null);
                if (!showAddVoiceForm && voiceFileInputRef.current) voiceFileInputRef.current.value = '';
              }}
              disabled={voiceUploading}
            >
              {showAddVoiceForm ? 'Отмена' : 'Добавить голос'}
            </Button>
          </div>
          {showAddVoiceForm && (
            <div className="space-y-3 rounded-lg border border-border bg-surface p-3">
              <input
                ref={voiceFileInputRef}
                type="file"
                accept=".wav,audio/wav"
                className="block w-full text-sm text-text file:mr-2 file:rounded file:border-0 file:bg-accent/20 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-primary"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  setVoiceUploadFile(f ?? null);
                  setVoiceUploadError(null);
                }}
              />
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-textSecondary mb-1">Имя (необязательно)</label>
                  <input
                    type="text"
                    className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent"
                    placeholder="Мой голос"
                    value={voiceUploadName}
                    onChange={(e) => setVoiceUploadName(e.target.value)}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-textSecondary mb-1">Роль (необязательно)</label>
                  <select
                    className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-accent"
                    value={voiceUploadRole}
                    onChange={(e) => setVoiceUploadRole((e.target.value || '') as 'narrator' | 'male' | 'female' | '')}
                  >
                    <option value="">—</option>
                    <option value="narrator">Диктор</option>
                    <option value="male">Мужской</option>
                    <option value="female">Женский</option>
                  </select>
                </div>
              </div>
              {voiceUploadError && (
                <p className="text-sm text-red-600 dark:text-red-400">{voiceUploadError}</p>
              )}
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={() => void handleUploadVoice()}
                disabled={!voiceUploadFile || voiceUploading}
              >
                {voiceUploading ? 'Загрузка…' : 'Загрузить'}
              </Button>
            </div>
          )}
          {customVoices.length > 0 && (
            <div className="space-y-2">
              <div className="text-sm font-medium text-text">Загруженные голоса</div>
              <ul className="space-y-1">
                {customVoices.map((v) => {
                  const isPlaying = playingVoiceId === v.id;
                  const isDeleting = deletingVoiceId === v.id;
                  return (
                    <li
                      key={v.id}
                      className="flex items-center gap-2 rounded-lg border border-border bg-surface px-3 py-2"
                    >
                      <div className="flex-1 min-w-0">
                        <span className="text-sm font-medium text-text">{v.name}</span>
                        <span className="ml-2 text-xs text-textSecondary">
                          {v.gender !== 'neutral' ? v.gender : 'диктор'}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handlePlayVoice(v)}
                        className="shrink-0 rounded p-1.5 text-textSecondary hover:bg-accent/20 transition-colors"
                        aria-label={isPlaying ? 'Остановить' : 'Прослушать'}
                      >
                        {isPlaying ? (
                          <Pause className="h-3.5 w-3.5 fill-current" />
                        ) : (
                          <Play className="h-3.5 w-3.5" />
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleDeleteVoice(v.id)}
                        disabled={isDeleting}
                        className="shrink-0 rounded p-1.5 text-textSecondary hover:text-red-600 hover:bg-red-100 dark:hover:bg-red-900/20 transition-colors disabled:opacity-50"
                        aria-label="Удалить голос"
                        title="Удалить голос"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Выбор голосов по ролям - на всю ширину */}
      {!isCompleted && (
        <div className="space-y-3">
          <div className="text-base font-medium text-text">Выбор голосов по ролям</div>
          <div className="text-xs text-textSecondary">
            Выберите по одному голосу для каждой роли. Нажмите кнопку воспроизведения для прослушивания.
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Диктор */}
          <div className="space-y-2">
            <div className="text-sm font-semibold text-text">🎙️ Диктор</div>
            <div className="h-64 overflow-y-auto rounded-lg border border-border bg-surfaceSoft p-2 space-y-1">
              {voicesByRole.narrator.length === 0 ? (
                <div className="text-xs text-textMuted py-2 text-center">Нет доступных дикторов</div>
              ) : (
                voicesByRole.narrator.map((v) => {
                  const isSelected = selectedVoiceIds.narrator === v.id;
                  const isPlaying = playingVoiceId === v.id;
                  return (
                    <div
                      key={v.id}
                      className={`flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer transition-colors ${
                        isSelected ? 'bg-accent/20 border border-accent' : 'hover:bg-surface'
                      }`}
                      onClick={(e) => {
                        // Если клик был на input, не обрабатываем здесь (input сам обработает)
                        if ((e.target as HTMLElement).tagName === 'INPUT') {
                          return;
                        }
                        handleSelectVoice('narrator', v.id);
                      }}
                    >
                      <input
                        type="radio"
                        checked={isSelected}
                        readOnly
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectVoice('narrator', v.id);
                        }}
                        className="cursor-pointer"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-text">{v.name}</div>
                        <div className="text-xs text-textSecondary">
                          {v.language} · {v.style}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePlayVoice(v);
                        }}
                        className="shrink-0 rounded p-1.5 text-textSecondary hover:bg-accent/20 transition-colors"
                        aria-label={isPlaying ? 'Остановить' : 'Прослушать'}
                      >
                        {isPlaying ? (
                          <Pause className="h-3.5 w-3.5 fill-current" />
                        ) : (
                          <Play className="h-3.5 w-3.5" />
                        )}
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Мужской голос */}
          <div className="space-y-2">
            <div className="text-sm font-semibold text-text">👨 Мужской голос</div>
            <div className="h-64 overflow-y-auto rounded-lg border border-border bg-surfaceSoft p-2 space-y-1">
              {voicesByRole.male.length === 0 ? (
                <div className="text-xs text-textMuted py-2 text-center">Нет доступных мужских голосов</div>
              ) : (
                voicesByRole.male.map((v) => {
                  const isSelected = selectedVoiceIds.male === v.id;
                  const isPlaying = playingVoiceId === v.id;
                  return (
                    <div
                      key={v.id}
                      className={`flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer transition-colors ${
                        isSelected ? 'bg-accent/20 border border-accent' : 'hover:bg-surface'
                      }`}
                      onClick={(e) => {
                        // Если клик был на input, не обрабатываем здесь (input сам обработает)
                        if ((e.target as HTMLElement).tagName === 'INPUT') {
                          return;
                        }
                        handleSelectVoice('male', v.id);
                      }}
                    >
                      <input
                        type="radio"
                        checked={isSelected}
                        readOnly
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectVoice('male', v.id);
                        }}
                        className="cursor-pointer"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-text">{v.name}</div>
                        <div className="text-xs text-textSecondary">
                          {v.language} · {v.style}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePlayVoice(v);
                        }}
                        className="shrink-0 rounded p-1.5 text-textSecondary hover:bg-accent/20 transition-colors"
                        aria-label={isPlaying ? 'Остановить' : 'Прослушать'}
                      >
                        {isPlaying ? (
                          <Pause className="h-3.5 w-3.5 fill-current" />
                        ) : (
                          <Play className="h-3.5 w-3.5" />
                        )}
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Женский голос */}
          <div className="space-y-2">
            <div className="text-sm font-semibold text-text">👩 Женский голос</div>
            <div className="h-64 overflow-y-auto rounded-lg border border-border bg-surfaceSoft p-2 space-y-1">
              {voicesByRole.female.length === 0 ? (
                <div className="text-xs text-textMuted py-2 text-center">Нет доступных женских голосов</div>
              ) : (
                voicesByRole.female.map((v) => {
                  const isSelected = selectedVoiceIds.female === v.id;
                  const isPlaying = playingVoiceId === v.id;
                  return (
                    <div
                      key={v.id}
                      className={`flex items-center gap-2 rounded-md px-2 py-1.5 cursor-pointer transition-colors ${
                        isSelected ? 'bg-accent/20 border border-accent' : 'hover:bg-surface'
                      }`}
                      onClick={(e) => {
                        // Если клик был на input, не обрабатываем здесь (input сам обработает)
                        if ((e.target as HTMLElement).tagName === 'INPUT') {
                          return;
                        }
                        handleSelectVoice('female', v.id);
                      }}
                    >
                      <input
                        type="radio"
                        checked={isSelected}
                        readOnly
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSelectVoice('female', v.id);
                        }}
                        className="cursor-pointer"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-text">{v.name}</div>
                        <div className="text-xs text-textSecondary">
                          {v.language} · {v.style}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePlayVoice(v);
                        }}
                        className="shrink-0 rounded p-1.5 text-textSecondary hover:bg-accent/20 transition-colors"
                        aria-label={isPlaying ? 'Остановить' : 'Прослушать'}
                      >
                        {isPlaying ? (
                          <Pause className="h-3.5 w-3.5 fill-current" />
                        ) : (
                          <Play className="h-3.5 w-3.5" />
                        )}
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          </div>
          </div>
        </div>
      )}

      {/* Озвучить фрагмент — показывается после загрузки книги (lastUploadedBookId / выбранная книга в App) */}
      {!isCompleted && isAppApiEnabled() && activeBookId && (
        <div className="space-y-4 rounded-2xl border border-border bg-surfaceSoft p-4">
          <div className="text-base font-medium text-text">Превью по спикерам</div>
          <p className="text-sm text-textSecondary">
            Получите три фрагмента (диктор, мужской, женский голос) для предпрослушивания перед полной озвучкой.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              disabled={
                previewLoading ||
                (!selectedVoiceIds.narrator && !selectedVoiceIds.male && !selectedVoiceIds.female)
              }
              onClick={() => void fetchPreviewFragments()}
            >
              {previewLoading ? 'Загрузка…' : 'Озвучить фрагмент'}
            </Button>
          </div>
          {previewError && (
            <p className="text-sm text-red-600 dark:text-red-400">{previewError}</p>
          )}
          {previewFragmentUrls && (previewFragmentUrls.narrator || previewFragmentUrls.male || previewFragmentUrls.female) && (
            <div className="space-y-4 pt-2">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {previewFragmentUrls.narrator && (
                  <div className="rounded-lg border border-border bg-surface p-3">
                    <div className="text-sm font-medium text-text mb-2">Диктор</div>
                    <audio controls className="w-full" src={previewFragmentUrls.narrator} />
                  </div>
                )}
                {previewFragmentUrls.male && (
                  <div className="rounded-lg border border-border bg-surface p-3">
                    <div className="text-sm font-medium text-text mb-2">Мужской голос</div>
                    <audio controls className="w-full" src={previewFragmentUrls.male} />
                  </div>
                )}
                {previewFragmentUrls.female && (
                  <div className="rounded-lg border border-border bg-surface p-3">
                    <div className="text-sm font-medium text-text mb-2">Женский голос</div>
                    <audio controls className="w-full" src={previewFragmentUrls.female} />
                  </div>
                )}
              </div>
              {/* Ползунки скорость и тембр — одна пара для всех спикеров (Вариант A) */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-text mb-1">
                    Скорость (tempo): {(speakerSettings.narrator?.tempo ?? 1).toFixed(2)}
                  </label>
                  <input
                    type="range"
                    min={0.7}
                    max={1.3}
                    step={0.05}
                    value={speakerSettings.narrator?.tempo ?? 1}
                    onChange={(e) => updateSpeakerSettingsTempoPitch(parseFloat(e.target.value), speakerSettings.narrator?.pitch ?? 0)}
                    className="w-full h-2 rounded-lg appearance-none bg-surfaceSoft accent-primary"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-text mb-1">
                    Тембр (pitch): {(speakerSettings.narrator?.pitch ?? 0).toFixed(2)}
                  </label>
                  <input
                    type="range"
                    min={-0.5}
                    max={0.5}
                    step={0.05}
                    value={speakerSettings.narrator?.pitch ?? 0}
                    onChange={(e) => updateSpeakerSettingsTempoPitch(speakerSettings.narrator?.tempo ?? 1, parseFloat(e.target.value))}
                    className="w-full h-2 rounded-lg appearance-none bg-surfaceSoft accent-primary"
                  />
                </div>
              </div>
              <Button
                variant="outline"
                disabled={previewLoading}
                onClick={() => void reFetchPreviewFragments()}
              >
                {previewLoading ? 'Запрос…' : 'Переозвучить фрагмент'}
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Секция загрузки файла и генерации */}
      {!isCompleted && (
        <div className="space-y-4">
          <input
            ref={fileInputRef}
            id={`file-input-${projectId}`}
            type="file"
            accept={ALLOWED_BOOK_EXTENSIONS.join(',')}
            multiple
            className="sr-only"
            onChange={handleFileSelect}
          />

          {/* Список загруженных файлов — показывается, если есть файлы в проекте, lastUploadedBookId, кэш или выбранные для загрузки */}
          {(projectBooks.length > 0 || uploadedFiles.length > 0 || (isAppApiEnabled() && lastUploadedBookId) || hasCachedFile(projectId)) ? (
            <div className="space-y-2">
              <div className="text-base font-medium text-text">Загруженные текстовые файлы</div>
              <div className="rounded-2xl border border-border bg-surfaceSoft p-4 space-y-2">
                {projectBooks.length > 0 ? projectBooks.map((book) => (
                  <div
                    key={book.id}
                    className="flex items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 py-2"
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <div className="rounded-full bg-accent/20 p-1 shrink-0">
                        <FileUp className="h-3.5 w-3.5 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-text truncate">
                          {book.title || book.id}
                          {book.status === 'done' && (
                            <span className="ml-2 text-xs text-green-600 dark:text-green-400">(озвучено)</span>
                          )}
                          {book.status === 'processing' && (
                            <span className="ml-2 text-xs text-amber-600 dark:text-amber-400">(в обработке)</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeProjectBook(book.id)}
                      className="shrink-0 rounded p-1 text-textSecondary hover:text-red-600 hover:bg-red-100 dark:hover:bg-red-900/20 transition-colors"
                      title="Удалить файл"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                )) : lastUploadedBookId ? (
                  <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 py-2">
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <div className="rounded-full bg-accent/20 p-1 shrink-0">
                        <FileUp className="h-3.5 w-3.5 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-text truncate">
                          Загруженный текст
                        </div>
                        <div className="text-xs text-textSecondary">ID: {lastUploadedBookId}</div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeProjectBook(lastUploadedBookId)}
                      className="shrink-0 rounded p-1 text-textSecondary hover:text-red-600 hover:bg-red-100 dark:hover:bg-red-900/20 transition-colors"
                      title="Удалить файл"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ) : null}
                {uploadedFiles.map((fileData) => (
                  <div
                    key={fileData.id}
                    className="flex items-center justify-between gap-2 rounded-lg border border-green-300/40 dark:border-green-700/40 bg-green-50/80 dark:bg-green-900/20 px-3 py-2"
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <div className="rounded-full bg-green-500/20 p-1 shrink-0">
                        <FileUp className="h-3.5 w-3.5 text-green-600 dark:text-green-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-text truncate">{fileData.name}</div>
                        <div className="text-xs text-textSecondary">
                          {(fileData.file.size / 1024).toFixed(2)} KB · {fileData.bookId ? 'загружен' : 'ожидает загрузки'}
                        </div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeFile(fileData.id)}
                      className="shrink-0 rounded p-1 text-textSecondary hover:text-red-600 hover:bg-red-100 dark:hover:bg-red-900/20 transition-colors"
                      title="Удалить файл"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={!canUploadFile}
                  className="w-full mt-2 inline-flex items-center justify-center gap-2 rounded-lg border-2 border-dashed border-accent/60 bg-accentSoft/10 px-4 py-2.5 text-sm font-medium text-primary dark:text-accent hover:bg-accentSoft/20 transition-colors disabled:opacity-50 disabled:pointer-events-none"
                >
                  <FileUp className="h-4 w-4" />
                  Добавить файлы
                </button>
              </div>
            </div>
          ) : (
            /* Зона drag-and-drop — только когда нет загруженных файлов */
            <div>
              <div className="text-base font-medium text-text mb-2">Перетащите или выберите текстовый файл с компьютера</div>
              <div
                onDragEnter={handleDragEnter}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`relative rounded-2xl border-2 border-dashed transition-all duration-200 ${
                  isDragging
                    ? 'border-accent bg-accentSoft/30 shadow-md'
                    : canUploadFile
                    ? 'border-accent/80 bg-accentSoft/20 cursor-pointer hover:border-accent hover:bg-accentSoft/30 hover:shadow-md'
                    : 'border-border bg-surfaceSoft opacity-50'
                }`}
              >
                <label
                  htmlFor={`file-input-${projectId}`}
                  className="flex flex-col items-center justify-center gap-4 p-10 min-h-[180px] cursor-pointer"
                >
                  <div className={`rounded-full p-4 transition-colors ${isDragging ? 'bg-accent/25' : 'bg-accent/15'}`}>
                    <FileUp className={`h-8 w-8 ${isDragging ? 'text-primary' : 'text-textSecondary'}`} />
                  </div>
                  <div className="text-center">
                    <div className={`text-base font-semibold font-heading ${isDragging ? 'text-primary' : 'text-text'}`}>
                      {isDragging ? 'Отпустите файлы для загрузки' : 'Перетащите файлы в область или выберите с устройства'}
                    </div>
                    <div className="mt-2 text-sm text-textSecondary">
                      Поддерживаются: <span className="font-medium text-text">.txt</span>, <span className="font-medium text-text">.fb2</span>, <span className="font-medium text-text">.epub</span>, <span className="font-medium text-text">.mobi</span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      openFileDialog();
                    }}
                    disabled={!canUploadFile}
                    className="mt-2 inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg border-2 border-primary dark:border-accent bg-surface px-4 py-2.5 text-sm font-semibold text-primary dark:text-accent transition-colors hover:bg-surfaceSoft hover:border-text disabled:pointer-events-none disabled:opacity-50"
                  >
                    <FileUp className="h-5 w-5" />
                    Выбрать файлы
                  </button>
                </label>
              </div>
            </div>
          )}

          {/* Кнопки действий */}
          <div className="flex flex-col items-center gap-2">
            {uploadError && (
              <p className="text-sm font-medium text-red-600 dark:text-red-400 animate-in fade-in">
                {uploadError}
              </p>
            )}
            <div className="flex justify-center gap-3">
              {uploadedFiles.length > 0 && (
                <Button
                  variant="outline"
                  disabled={!canUploadFile || uploadInProgress}
                  onClick={processFiles}
                  className={
                    uploadSuccess
                      ? 'border-green-500 bg-green-50 text-green-700 dark:border-green-600 dark:bg-green-900/20 dark:text-green-400'
                      : ''
                  }
                >
                  {uploadInProgress
                    ? 'Загрузка…'
                    : uploadSuccess
                      ? 'Файлы загружены'
                      : 'Загрузить файлы на сервер'}
                </Button>
              )}
              {isAppApiEnabled() && (lastUploadedBookId ?? projectBooks[0]?.id) && (
                <label className="flex items-center gap-2 text-sm text-textSecondary cursor-pointer">
                  <input
                    type="checkbox"
                    checked={forceReSynthesize}
                    onChange={(e) => setForceReSynthesize(e.target.checked)}
                    className="rounded border-border"
                  />
                  Принудительно переозвучить (отправить все строки в stage4)
                </label>
              )}
              <Button
                disabled={
                  generating ||
                  !canEdit ||
                  (uploadedFiles.length === 0 && (!isAppApiEnabled() || !(lastUploadedBookId ?? projectBooks[0]?.id)))
                }
                onClick={generateAudio}
              >
                {generating ? 'Запускаем…' : 'Сгенерировать озвучку'}
              </Button>
            </div>
          </div>

          {/* Прогресс-бар: при App — по GET /books/{book_id}/status, при Nest — по статусу проекта */}
          {isProcessing && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-textSecondary">Обработка и озвучка</span>
                <span className="font-medium text-text">{processingProgress}%</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-surfaceSoft">
                <div
                  className="h-full bg-gradient-to-r from-accent to-accentWarm transition-all duration-300 ease-out"
                  style={{ width: `${processingProgress}%` }}
                />
              </div>
              <div className="text-xs text-textSecondary">
                {processingProgress < 20 && 'Запуск пайплайна...'}
                {processingProgress >= 20 && processingProgress < 50 && 'Анализ текста, распределение голосов...'}
                {processingProgress >= 50 && processingProgress < 80 && 'Генерация аудио (TTS)...'}
                {processingProgress >= 80 && processingProgress < 100 && 'Сборка аудио...'}
                {processingProgress === 100 && 'Обработка завершена!'}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Предпрослушать результат */}
      <div className="rounded-2xl border border-border bg-surfaceSoft p-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="font-medium text-text">Предпрослушать результат</div>
            <div className="mt-1 text-sm text-textSecondary">
              Прослушайте готовые фрагменты предварительной озвучки перед отправкой на полную обработку.
            </div>
          </div>
          <button onClick={() => loadAll()} className="text-sm text-primary dark:text-accent hover:text-text hover:underline transition-colors">
            Обновить
          </button>
        </div>

        <div className="mt-4 space-y-3">
          {isAppApiEnabled() && lastUploadedBookId && chaptersReadyFromApp.length >= 1 && (
            <div className="rounded-lg border border-border bg-surface p-3 space-y-2">
              <div className="text-sm font-medium text-text">Главы готовы к прослушиванию</div>
              <p className="text-xs text-textSecondary">
                Можно слушать готовые главы, не дожидаясь полной озвучки книги.
              </p>
              <div className="flex flex-wrap gap-2">
                {chaptersReadyFromApp.map((num) => {
                  const chapterSrc = getBookChapterAudioUrl(lastUploadedBookId, num);
                  if (!chapterSrc) return null;
                  return (
                    <audio
                      key={num}
                      controls
                      className="w-full min-w-[200px]"
                      src={chapterSrc}
                      title={`Глава ${num}`}
                    />
                  );
                })}
              </div>
              <div className="flex flex-wrap gap-1 pt-1">
                {chaptersReadyFromApp.map((num) => (
                  <span key={num} className="text-xs px-2 py-0.5 rounded bg-surfaceSoft text-textSecondary">
                    Глава {num}
                  </span>
                ))}
              </div>
            </div>
          )}
          {isAppApiEnabled() && finalBookAudioUrl ? (
            <div className="rounded-lg border border-border bg-surface p-3">
              <div className="text-sm font-medium text-text mb-2">Финальное аудио книги</div>
              <audio controls className="w-full" src={finalBookAudioUrl} onPlay={() => setHasListenedToFinalAudio(true)} />
            </div>
          ) : previewAudios.length === 0 ? (
            <div className="text-sm text-textSecondary text-center py-4">
              Пока нет готовых фрагментов для прослушивания.
            </div>
          ) : (
            previewAudios.map((audio) => {
              const audioSrc = `${API_BASE}/api/audios/${audio.id}/stream`;
              return (
                <div key={audio.id} className="rounded-lg border border-border bg-surface p-3">
                  <div className="flex items-center justify-between gap-4 mb-2">
                    <div className="text-sm font-medium text-text">
                      Фрагмент {audio.id.slice(0, 8)}…
                    </div>
                    <div className="text-xs text-textMuted">
                      {new Date(audio.createdAt).toLocaleString()}
                    </div>
                  </div>
                  <audio controls className="w-full" src={audioSrc} onPlay={() => setHasListenedToFinalAudio(true)} />
                </div>
              );
            })
          )}
        </div>
      </div>


      {/* Кнопка отправки на полную обработку - показывается только когда основные шаги выполнены */}
      {!isCompleted && (() => {
        const hasVoices = selectedVoiceIds.narrator || selectedVoiceIds.male || selectedVoiceIds.female;
        const hasFiles = uploadedFiles.length > 0 || (isAppApiEnabled() && lastUploadedBookId);
        const hasPreviewAudios = previewAudios.length > 0 || (isAppApiEnabled() && finalBookAudioUrl);
        const canSendToFullProcessing = hasVoices && hasFiles && hasPreviewAudios;
        
        return canSendToFullProcessing ? (
          <div className="mt-6 pt-6 border-t border-border space-y-4">
            <Button
              variant="primary"
              className="w-full"
              onClick={generateFullAudiobook}
              disabled={completing || isFullProcessing}
            >
              {completing ? 'Отправка…' : isFullProcessing ? 'Обработка…' : 'Отправить книгу на полную обработку и озвучку'}
            </Button>
            
            {/* Статус-бар полной обработки */}
            {isFullProcessing && (
              <div className="rounded-lg border border-border bg-surfaceSoft p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-sm font-medium text-text">
                    {fullProcessingStatus === 'queued' && 'Ожидание обработки...'}
                    {fullProcessingStatus === 'processing' && 'Идет обработка книги...'}
                    {fullProcessingStatus === 'ready' && 'Обработка завершена'}
                    {fullProcessingStatus === 'error' && 'Ошибка обработки'}
                  </div>
                  {fullProcessingStatus === 'processing' && (
                    <div className="text-xs text-textMuted">{fullProcessingProgress}%</div>
                  )}
                </div>
                {(fullProcessingStatus === 'queued' || fullProcessingStatus === 'processing') && (
                  <div className="w-full h-2 bg-surface rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-accent to-accentWarm transition-all duration-300 ease-out"
                      style={{
                        width: fullProcessingStatus === 'queued' ? '10%' : `${fullProcessingProgress}%`,
                      }}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        ) : null;
      })()}
      
      {/* Секция со списком глав после завершения обработки */}
      {(chapters.length > 0 || chaptersError) && (
        <div className="mt-6 rounded-2xl border border-border bg-surfaceSoft p-4">
          <div className="mb-4">
            <div className="font-medium text-text">Главы книги</div>
            <div className="mt-1 text-sm text-textSecondary">
              Прослушайте все главы перед созданием финальной аудио книги.
            </div>
          </div>
          {chaptersError ? (
            <p className="text-sm text-amber-600 dark:text-amber-400">{chaptersError}</p>
          ) : null}
          <div className="space-y-3">
            {chapters.map((chapter) => {
              const chapterAudioSrc = chapter.audioId
                ? `${API_BASE}/api/audios/${chapter.audioId}/stream`
                : undefined;
              return (
                <div key={chapter.id} className="rounded-lg border border-border bg-surface p-3">
                  <div className="flex items-center justify-between gap-4 mb-2">
                    <div className="text-sm font-medium text-text">{chapter.title}</div>
                    {chapter.durationSeconds && (
                      <div className="text-xs text-textMuted">
                        {Math.floor(chapter.durationSeconds / 60)}:{(chapter.durationSeconds % 60).toString().padStart(2, '0')}
                      </div>
                    )}
                  </div>
                  {chapterAudioSrc ? (
                    <audio controls className="w-full" src={chapterAudioSrc} />
                  ) : (
                    <div className="text-sm text-textSecondary text-center py-2">
                      Аудио пока не готово
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
      
      {/* Кнопка создания аудио книги — показывается только при наличии финального аудио и после прослушивания */}
      {(() => {
        const hasFinalAudio = (isAppApiEnabled() && finalBookAudioUrl) || (!isAppApiEnabled() && previewAudios.length > 0);
        if (!hasFinalAudio || !hasListenedToFinalAudio || isCompleted) return null;
        return (
          <div className="mt-6 pt-6 border-t border-border">
            <Button
              variant="primary"
              className="w-full bg-green-600 hover:bg-green-700 text-white focus-visible:ring-green-500"
              onClick={() => setShowCreateBookConfirm(true)}
              disabled={creatingBook}
            >
              {creatingBook ? 'Создание…' : 'Создать аудио книгу'}
            </Button>
          </div>
        );
      })()}
      
      {/* Модальное окно подтверждения создания книги */}
      {showCreateBookConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="rounded-2xl border border-border bg-surfaceSoft p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold text-text mb-2">Подтверждение создания аудио книги</h3>
            <p className="text-sm text-textSecondary mb-6">
              После создания аудио книги редактирование проекта будет невозможно. Вы уверены, что хотите продолжить?
            </p>
            <div className="flex gap-3">
              <Button
                variant="secondary"
                className="flex-1"
                onClick={() => setShowCreateBookConfirm(false)}
                disabled={creatingBook}
              >
                Отмена
              </Button>
              <Button
                variant="primary"
                className="flex-1 bg-green-600 hover:bg-green-700 text-white focus-visible:ring-green-500"
                onClick={createBook}
                disabled={creatingBook}
              >
                {creatingBook ? 'Создание…' : 'Создать книгу'}
              </Button>
            </div>
          </div>
        </div>
      )}
      </div>

      {/* Боковая панель прогресса и кнопки управления */}
      <div className="hidden lg:block sticky top-6 h-fit space-y-6">
        <ProjectProgressSidebar steps={progressSteps} />
        
        {/* Кнопки управления проектом */}
        {!isCompleted && (
          <div className="rounded-2xl border border-border bg-surfaceSoft p-6 space-y-4">
            <Button
              variant="secondary"
              className="w-full"
              disabled={saving || !canEdit}
              onClick={saveProject}
            >
              {saving ? 'Сохраняем…' : 'Сохранить работу над проектом'}
            </Button>
            
            {showDeleteConfirm ? (
              <div className="flex items-center gap-1 rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-900/20 overflow-hidden">
                <button
                  type="button"
                  onClick={deleteProject}
                  disabled={deleting}
                  className="flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 disabled:opacity-50"
                  aria-label="Подтвердить удаление"
                >
                  <Check className="h-3.5 w-3.5" />
                  Подтвердить
                </button>
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={deleting}
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
                onClick={() => setShowDeleteConfirm(true)}
                disabled={deleting}
                className="w-full rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-900/20 px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 disabled:opacity-50 transition-colors flex items-center justify-center gap-2"
                aria-label="Удалить проект"
              >
                <Trash2 className="h-4 w-4" />
                Удалить проект
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

