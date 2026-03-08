'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, FileUp, Pause, Pencil, Play, Trash2, X } from 'lucide-react';
import { apiJson } from '../../../../lib/api';
import { getAccessToken, getStoredUserId } from '../../../../lib/auth';
import { isAppApiEnabled, getAppApiUrl, getBookChapterAudioUrl, listVoices, listBooksByProject, appFetch, appJson, putAudioConfigVoiceIds, processBookStage4, getBookStatus, downloadBookAudio, deleteBook, deleteBooksByProject, type AppBook, type TtsEngine } from '../../../../lib/app-api';
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
};
type AudioItem = { id: string; status: string; format?: string | null; durationSeconds?: number | null; createdAt: string };
type Chapter = { id: string; title: string; audioId?: string; durationSeconds?: number; createdAt: string };

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

  async function loadChapters() {
    try {
      // Пытаемся загрузить главы через API
      const data = await apiJson<{ chapters: Chapter[] }>(`/api/projects/${projectId}/chapters`);
      setChapters(data.chapters);
    } catch (e: any) {
      // Если endpoint не существует, используем заглушку для тестирования
      console.warn('Endpoint для глав не найден, используем заглушку:', e);
      
      // Заглушка для тестирования проекта cmltq0vo80001p1p0180h5qhu
      if (projectId === 'cmltq0vo80001p1p0180h5qhu') {
        setChapters([
          {
            id: 'chapter-1',
            title: 'Глава 1: Начало пути',
            audioId: 'mock-audio-1',
            durationSeconds: 120,
            createdAt: new Date().toISOString(),
          },
          {
            id: 'chapter-2',
            title: 'Глава 2: Развитие событий',
            audioId: 'mock-audio-2',
            durationSeconds: 95,
            createdAt: new Date(Date.now() - 60000).toISOString(),
          },
          {
            id: 'chapter-3',
            title: 'Глава 3: Кульминация',
            audioId: 'mock-audio-3',
            durationSeconds: 150,
            createdAt: new Date(Date.now() - 120000).toISOString(),
          },
        ]);
      } else {
        // Для других проектов просто не показываем главы
        setChapters([]);
      }
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
            if (appVoices.length > 0) return mapAppVoicesToVoice(appVoices);
          } catch (e) {
            console.warn('[Voices] FastAPI /voices failed, falling back to Nest:', e);
          }
        }
        try {
          const r = await apiJson<{ voices?: Voice[] }>('/api/voices');
          return (r.voices ?? []) as Voice[];
        } catch {
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
          setProjectBooks(books);
          if (books.length > 0) setLastUploadedBookId(books[books.length - 1].id);
          // Загружаем финальный WAV, если есть готовое аудио
          const bookWithAudio = books.find((b) => b.final_audio_path);
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
          const audioSettings = await appJson<{ config?: { tts_engine?: string } }>('/books/settings/audio').catch(() => ({ config: {} }));
          const engine = audioSettings?.config?.tts_engine;
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

      if (projectVoices.length > 0) {
        for (const pv of projectVoices) {
          const voice = voicesList.find((vo) => vo.id === pv.voiceId);
          if (voice) {
            if (voice.role === 'narrator' && !initialVoices.narrator) initialVoices.narrator = voice.id;
            else if (voice.gender === 'male' && !initialVoices.male) initialVoices.male = voice.id;
            else if (voice.gender === 'female' && !initialVoices.female) initialVoices.female = voice.id;
          }
        }
      } else {
        if (isAppApiEnabled()) {
          const byId = (id: string) => voicesList.find((v) => v.id === id)?.id ?? voicesList[0]?.id;
          if (voicesList.length > 0) {
            if (!initialVoices.narrator) initialVoices.narrator = byId('narrator');
            if (!initialVoices.male) initialVoices.male = byId('male');
            if (!initialVoices.female) initialVoices.female = byId('female');
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

  async function generateAudio() {
    const hasFiles = uploadedFiles.length > 0 || (isAppApiEnabled() && lastUploadedBookId);
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
    if (appApiUrl && lastUploadedBookId) {
      if (finalBookAudioUrlRef.current) {
        URL.revokeObjectURL(finalBookAudioUrlRef.current);
        finalBookAudioUrlRef.current = null;
      }
      setFinalBookAudioUrl(null);
      setChaptersReadyFromApp([]);
      try {
        await putAudioConfigVoiceIds(selectedVoiceIds, { ttsEngine });
        await processBookStage4(lastUploadedBookId, 500, selectedVoiceIds, ttsEngine);
        startAppProgressTracking(lastUploadedBookId);
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
      // Начинаем отслеживание статуса полной обработки
      startFullProcessingTracking();
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось отправить книгу на полную обработку');
      setIsFullProcessing(false);
      setFullProcessingStatus('error');
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

    const appApiUrl = process.env.NEXT_PUBLIC_APP_API_URL ?? '';

    try {
      if (appApiUrl) {
        const bookIds: string[] = [];
        const userId = getStoredUserId() ?? (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_DEV_USER_ID) ?? 'anonymous';
        for (const fileData of uploadedFiles) {
          const formData = new FormData();
          formData.append('file', fileData.file);
          if (project?.title?.trim()) formData.append('project_title', project.title.trim());
          const response = await fetch(`${appApiUrl.replace(/\/$/, '')}/api/books/upload`, {
            method: 'POST',
            headers: {
              'X-User-Id': userId,
              'X-Project-Id': projectId,
            },
            body: formData,
          });

          if (response.status === 422) {
            setUploadError('Загрузка не удалась, повторите попытку');
            uploadErrorTimeoutRef.current = setTimeout(() => {
              setUploadError(null);
              uploadErrorTimeoutRef.current = null;
            }, 15000);
            return;
          }

          if (!response.ok) {
            const text = await response.text();
            let msg = text;
            try {
              const j = JSON.parse(text);
              if (typeof (j as { detail?: string }).detail === 'string') msg = (j as { detail: string }).detail;
            } catch {}
            setUploadError('Загрузка не удалась, повторите попытку');
            uploadErrorTimeoutRef.current = setTimeout(() => {
              setUploadError(null);
              uploadErrorTimeoutRef.current = null;
            }, 15000);
            return;
          }

          const data = (await response.json()) as { id?: string; status?: string };
          if (typeof data?.id === 'string') bookIds.push(data.id);
        }
        setUploadedFiles((prev) => prev.map((f, i) => ({ ...f, bookId: bookIds[i] ?? f.bookId })));
        if (bookIds.length > 0) setLastUploadedBookId(bookIds[bookIds.length - 1]);
        setUploadSuccess(true);
        await loadAll({ silent: true });
        setUploadedFiles([]);
        return;
      }

      // Fallback: загрузка в Nest API (проекты)
      for (const fileData of uploadedFiles) {
        await cacheProjectFile(projectId, fileData.file);
      }

      const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:4000';
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
          throw new Error(`Ошибка загрузки файла ${fileData.name}: ${text || 'Не удалось загрузить файл'}`);
        }
      }

      setUploadSuccess(true);
      await loadAll({ silent: true });
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось загрузить файлы');
      setUploadError('Загрузка не удалась, повторите попытку');
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

  function getVoiceSampleUrl(voiceId: string): string | null {
    if (isAppApiEnabled()) return null;
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:4000';
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
        completed: step1Completed,
        active: activeStepId === 1,
      },
      {
        id: 2,
        title: 'Отправьте на предварительную озвучку',
        completed: step2Completed,
        active: activeStepId === 2,
      },
      {
        id: 3,
        title: 'Прослушайте получившийся предварительный результат',
        completed: step3Completed,
        active: activeStepId === 3,
      },
      {
        id: 4,
        title: 'Создайте итоговую аудио-книгу',
        completed: step4Completed,
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
              <Button
                disabled={
                  generating ||
                  !canEdit ||
                  (uploadedFiles.length === 0 && (!isAppApiEnabled() || !lastUploadedBookId))
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
          <button onClick={loadAll} className="text-sm text-primary dark:text-accent hover:text-text hover:underline transition-colors">
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
                {chaptersReadyFromApp.map((num) => (
                  <audio
                    key={num}
                    controls
                    className="w-full min-w-[200px]"
                    src={getBookChapterAudioUrl(lastUploadedBookId, num)}
                    title={`Глава ${num}`}
                  />
                ))}
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
              const audioSrc = `${process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:4000'}/api/audios/${audio.id}/stream`;
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
      {chapters.length > 0 && (
        <div className="mt-6 rounded-2xl border border-border bg-surfaceSoft p-4">
          <div className="mb-4">
            <div className="font-medium text-text">Главы книги</div>
            <div className="mt-1 text-sm text-textSecondary">
              Прослушайте все главы перед созданием финальной аудио книги.
            </div>
          </div>
          
          <div className="space-y-3">
            {chapters.map((chapter) => {
              const chapterAudioSrc = chapter.audioId
                ? `${process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:4000'}/api/audios/${chapter.audioId}/stream`
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

