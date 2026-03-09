'use client';

import Link from 'next/link';
import { useEffect, useState, useRef } from 'react';
import { Pencil, Image as ImageIcon, Save, X, Trash2, Check, Download, Play } from 'lucide-react';
import { apiJson, API_BASE } from '../../../lib/api';
import {
  isAppApiEnabled,
  listBooks,
  getBookStatus,
  deleteBook as appDeleteBook,
  downloadBookAudio,
  getAudiobookStreamBlob,
  processBookStage4,
} from '../../../lib/app-api';
import { Button } from '../../../components/ui';

type Book = {
  id: string;
  projectId: string;
  title: string;
  description?: string | null;
  author?: string | null;
  genre?: string | null;
  seriesId?: string | null;
  seriesName?: string | null;
  seriesOrder?: number | null;
  coverImageUrl?: string | null;
  language: string;
  completedAt?: string;
  updatedAt: string;
  audio?: {
    id: string;
    status: string;
    format?: string | null;
    durationSeconds?: number | null;
    streamUrl: string;
  } | null;
  /** Книга из App API (Python backend) */
  fromApp?: boolean;
  /** ID книги в App API для воспроизведения/скачивания (Nest-книги, созданные из проекта) */
  appBookId?: string | null;
  /** Папка в storage/audiobooks после finalize — воспроизведение через App API stream */
  audiobookFolder?: string | null;
  status?: string;
  final_audio_path?: string | null;
  progress?: number;
  total_lines?: number;
  tts_done?: number;
};

// Список общепринятых жанров книг
const BOOK_GENRES = [
  'Фантастика',
  'Фэнтези',
  'Детектив',
  'Триллер',
  'Роман',
  'Любовный роман',
  'Исторический роман',
  'Приключения',
  'Ужасы',
  'Мистика',
  'Научная фантастика',
  'Биография',
  'Автобиография',
  'Мемуары',
  'Документальная литература',
  'Публицистика',
  'Поэзия',
  'Драма',
  'Комедия',
  'Трагедия',
  'Детская литература',
  'Подростковая литература',
  'Юмор',
  'Саморазвитие',
  'Бизнес',
  'Философия',
  'Религия',
  'Эзотерика',
  'Кулинария',
  'Путешествия',
  'Спорт',
  'Образование',
  'Наука',
  'Техника',
  'Искусство',
  'Музыка',
  'Кино',
  'Игры',
  'Хобби',
  'Другое',
] as const;

type TrashedBook = {
  id: string;
  title: string;
  language: string;
  deletedAt: string;
};

export default function BooksPage() {
  const [books, setBooks] = useState<Book[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingBookId, setEditingBookId] = useState<string | null>(null);
  const [editingBook, setEditingBook] = useState<Partial<Book> | null>(null);
  const [availableSeries, setAvailableSeries] = useState<Array<{ id: string; name: string; bookCount: number }>>([]);
  const [loadingSeries, setLoadingSeries] = useState(false);
  const [showCreateSeries, setShowCreateSeries] = useState(false);
  const [newSeriesName, setNewSeriesName] = useState('');
  const [saving, setSaving] = useState(false);
  const [uploadingCover, setUploadingCover] = useState<string | null>(null);
  const coverInputRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [expandedDeleteId, setExpandedDeleteId] = useState<string | null>(null);
  const [showTrash, setShowTrash] = useState(false);
  const [trash, setTrash] = useState<TrashedBook[]>([]);
  const [trashLoading, setTrashLoading] = useState(false);
  const [restoringId, setRestoringId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [startingTtsId, setStartingTtsId] = useState<string | null>(null);
  const [appBookPlaybackUrls, setAppBookPlaybackUrls] = useState<Record<string, string>>({});
  const appBooksPollRef = useRef<NodeJS.Timeout | null>(null);

  async function loadBooks() {
    setLoading(true);
    setError(null);
    try {
      // Сначала пробуем загрузить книги из Nest API (GET /api/books)
      try {
        const data = await apiJson<{ books: Book[]; total?: number }>('/api/books');
        if (data.books && data.books.length >= 0) {
          setBooks(data.books);
          return;
        }
      } catch (_) {
        // Nest API недоступен или ошибка — fallback ниже
      }

      if (isAppApiEnabled()) {
        const appBooks = await listBooks();
        const withStatus = await Promise.all(
          appBooks.map(async (b) => {
            try {
              const st = await getBookStatus(b.id);
              return {
                id: b.id,
                projectId: b.id,
                title: b.title,
                description: null,
                author: null,
                coverImageUrl: null,
                language: 'ru',
                updatedAt: b.created_at,
                audio: b.final_audio_path ? { id: '', status: 'ready', streamUrl: '', format: null, durationSeconds: null } : null,
                fromApp: true as const,
                status: b.status,
                final_audio_path: b.final_audio_path,
                progress: st.progress,
                total_lines: st.total_lines,
                tts_done: st.tts_done,
              } as Book;
            } catch {
              return {
                id: b.id,
                projectId: b.id,
                title: b.title,
                description: null,
                author: null,
                coverImageUrl: null,
                language: 'ru',
                updatedAt: b.created_at,
                audio: null,
                fromApp: true as const,
                status: b.status,
                final_audio_path: b.final_audio_path,
                progress: 0,
                total_lines: 0,
                tts_done: 0,
              } as Book;
            }
          })
        );
        setBooks(withStatus);
        return;
      }

      const projectsData = await apiJson<{ projects: Array<{ id: string; title: string; language: string; status: string; updatedAt: string }> }>('/api/projects');
      const projects = projectsData.projects.filter((p) => p.status === 'completed') || [];
      const booksData: Book[] = await Promise.all(
        projects.map(async (project) => {
          try {
            const audiosData = await apiJson<{ audios: Array<{ id: string; status: string; format?: string | null; durationSeconds?: number | null }> }>(`/api/projects/${project.id}/audios`);
            const readyAudio = audiosData.audios?.find((a) => a.status === 'ready');
            return {
              id: project.id,
              projectId: project.id,
              title: project.title,
              description: null,
              author: null,
              coverImageUrl: null,
              language: project.language,
              updatedAt: project.updatedAt,
              audio: readyAudio ? {
                id: readyAudio.id,
                status: readyAudio.status,
                format: readyAudio.format,
                durationSeconds: readyAudio.durationSeconds,
                streamUrl: `/api/audios/${readyAudio.id}/stream`,
              } : null,
            };
          } catch {
            return {
              id: project.id,
              projectId: project.id,
              title: project.title,
              description: null,
              author: null,
              coverImageUrl: null,
              language: project.language,
              updatedAt: project.updatedAt,
              audio: null,
            };
          }
        })
      );
      setBooks(booksData);
    } catch (e: any) {
      setError(e?.message ?? 'Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  }

  async function loadTrash() {
    setTrashLoading(true);
    setError(null);
    try {
      const data = await apiJson<{ books: TrashedBook[] }>('/api/books/trash');
      setTrash(data.books ?? []);
    } catch {
      setTrash([]);
    } finally {
      setTrashLoading(false);
    }
  }

  async function deleteBook(id: string, _title: string, book?: Book) {
    setExpandedDeleteId(null);
    setDeletingId(id);
    setError(null);
    try {
      if (book?.fromApp) {
        await appDeleteBook(id);
      } else {
        await apiJson(`/api/books/${id}`, { method: 'DELETE' });
      }
      setBooks((prev) => prev.filter((b) => b.id !== id));
      setAppBookPlaybackUrls((prev) => {
        const url = prev[id];
        if (url) URL.revokeObjectURL(url);
        const next = { ...prev };
        delete next[id];
        return next;
      });
      if (showTrash && !book?.fromApp) loadTrash();
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось удалить книгу');
    } finally {
      setDeletingId(null);
    }
  }

  async function handleDownloadAppBook(book: Book) {
    const bookId = book.audiobookFolder ? book.id : book.appBookId!;
    setDownloadingId(book.id);
    setError(null);
    try {
      const { blob, filename } = book.audiobookFolder
        ? await getAudiobookStreamBlob(book.audiobookFolder)
        : await downloadBookAudio(bookId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = book.audiobookFolder ? (book.title.replace(/[<>:"/\\|?*]/g, '_') + '.wav') : filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось скачать аудио');
    } finally {
      setDownloadingId(null);
    }
  }

  async function loadAppBookPlayback(bookId: string, book: Book) {
    if (appBookPlaybackUrls[bookId]) return;
    setError(null);
    try {
      const { blob } = book.audiobookFolder
        ? await getAudiobookStreamBlob(book.audiobookFolder)
        : await downloadBookAudio(book.appBookId!);
      const url = URL.createObjectURL(blob);
      setAppBookPlaybackUrls((prev) => ({ ...prev, [bookId]: url }));
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось загрузить аудио для воспроизведения');
    }
  }

  async function handleStartTtsAppBook(bookId: string) {
    setStartingTtsId(bookId);
    setError(null);
    try {
      await processBookStage4(bookId, 500);
      await loadBooks();
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось запустить озвучку');
    } finally {
      setStartingTtsId(null);
    }
  }

  async function restoreBook(id: string) {
    setRestoringId(id);
    setError(null);
    try {
      const data = await apiJson<{ book: Book }>(`/api/books/${id}/restore`, { method: 'POST' });
      setTrash((prev) => prev.filter((b) => b.id !== id));
      setBooks((prev) => [data.book, ...prev]);
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось восстановить книгу');
    } finally {
      setRestoringId(null);
    }
  }

  function formatTrashRemaining(deletedAt: string) {
    const hoursSince = (Date.now() - new Date(deletedAt).getTime()) / (60 * 60 * 1000);
    const remaining = Math.max(0, Math.ceil(168 - hoursSince)); // 7 дней = 168 часов
    if (remaining >= 24) return `Осталось ~${Math.ceil(remaining / 24)} д`;
    return `Осталось ~${remaining} ч`;
  }

  useEffect(() => {
    void loadBooks();
  }, []);

  const appBookPlaybackUrlsRef = useRef<Record<string, string>>({});
  appBookPlaybackUrlsRef.current = appBookPlaybackUrls;
  useEffect(() => {
    return () => {
      Object.values(appBookPlaybackUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
    };
  }, []);

  // Опрос статуса книг из App, пока есть книги в обработке
  useEffect(() => {
    if (!isAppApiEnabled()) return;
    const inProgress = books.filter(
      (b) => b.fromApp && b.status && !['completed', 'error'].includes(b.status)
    );
    if (inProgress.length === 0) return;
    const interval = setInterval(async () => {
      const updates = await Promise.all(
        inProgress.map(async (b) => {
          try {
            const st = await getBookStatus(b.id);
            return { id: b.id, ...st };
          } catch {
            return null;
          }
        })
      );
      setBooks((prev) =>
        prev.map((book) => {
          const u = updates.find((x) => x && x.id === book.id);
          if (!u || !book.fromApp) return book;
          return {
            ...book,
            status: u.stage === 'stage5' ? 'assembling' : u.stage,
            progress: u.progress,
            total_lines: u.total_lines,
            tts_done: u.tts_done,
          };
        })
      );
    }, 3000);
    appBooksPollRef.current = interval;
    return () => {
      if (appBooksPollRef.current) clearInterval(appBooksPollRef.current);
    };
  }, [books.filter((b) => b.fromApp).map((b) => `${b.id}:${b.status ?? ''}`).join(',')]);

  function getAudioUrl(streamUrl: string): string {
    const base = API_BASE;
    return streamUrl.startsWith('http') ? streamUrl : `${base}${streamUrl}`;
  }

  function getCoverUrl(book: Book): string | null {
    if (book.coverImageUrl) {
      const base = API_BASE;
      return book.coverImageUrl.startsWith('http') ? book.coverImageUrl : `${base}${book.coverImageUrl}`;
    }
    return null;
  }

  function formatDuration(seconds: number | null | undefined): string {
    if (!seconds) return '—';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
  }

  async function loadSeries() {
    setLoadingSeries(true);
    try {
      const data = await apiJson<{ series: Array<{ id: string; name: string; bookCount: number }> }>('/api/books/series');
      setAvailableSeries(data.series || []);
    } catch (e: any) {
      // Если endpoint не реализован, используем пустой массив
      console.warn('Endpoint для серий не найден:', e);
      setAvailableSeries([]);
    } finally {
      setLoadingSeries(false);
    }
  }

  async function createSeries(name: string) {
    try {
      const data = await apiJson<{ series: { id: string; name: string } }>('/api/books/series', {
        method: 'POST',
        body: JSON.stringify({ name }),
      });
      await loadSeries();
      setShowCreateSeries(false);
      setNewSeriesName('');
      return data.series.id;
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось создать серию');
      return null;
    }
  }

  async function startEditing(book: Book) {
    setEditingBookId(book.id);
    setEditingBook({
      title: book.title,
      description: book.description || '',
      author: book.author || '',
      genre: book.genre || '',
      seriesId: book.seriesId || '',
      seriesOrder: book.seriesOrder || null,
    });
    // Загружаем доступные серии при открытии редактирования
    await loadSeries();
  }

  function cancelEditing() {
    setEditingBookId(null);
    setEditingBook(null);
    setShowCreateSeries(false);
    setNewSeriesName('');
  }

  async function saveBook(bookId: string) {
    if (!editingBook) return;

    setSaving(true);
    setError(null);
    try {
      // Если выбрана новая серия, создаем её сначала
      let seriesId = editingBook.seriesId;
      if (showCreateSeries && newSeriesName.trim()) {
        const createdSeriesId = await createSeries(newSeriesName.trim());
        if (createdSeriesId) {
          seriesId = createdSeriesId;
        } else {
          setSaving(false);
          return;
        }
      }

      const data = await apiJson<{ book: Book }>(`/api/books/${bookId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          title: editingBook.title,
          description: editingBook.description || null,
          author: editingBook.author || null,
          genre: editingBook.genre || null,
          seriesId: seriesId || null,
          seriesOrder: editingBook.seriesOrder || null,
        }),
      });
      
      setBooks((prev) => prev.map((b) => (b.id === bookId ? data.book : b)));
      setEditingBookId(null);
      setEditingBook(null);
      setShowCreateSeries(false);
      setNewSeriesName('');
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось сохранить изменения');
    } finally {
      setSaving(false);
    }
  }

  async function handleCoverUpload(bookId: string, file: File) {
    setUploadingCover(bookId);
    setError(null);
    
    try {
      const formData = new FormData();
      formData.append('file', file);

      const base = API_BASE;
      const token = localStorage.getItem('neurochtec_access_token');
      
      const response = await fetch(`${base}/api/books/${bookId}/cover`, {
        method: 'POST',
        headers: {
          'Authorization': token ? `Bearer ${token}` : '',
        },
        body: formData,
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Не удалось загрузить обложку');
      }

      const data = await response.json();
      setBooks((prev) => prev.map((b) => (b.id === bookId ? { ...b, coverImageUrl: data.book.coverImageUrl } : b)));
    } catch (e: any) {
      setError(e?.message ?? 'Не удалось загрузить обложку');
    } finally {
      setUploadingCover(null);
    }
  }

  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-heading text-2xl font-semibold text-text">Мои книги</h1>
          <p className="mt-1 text-sm text-textSecondary">
            Здесь хранятся ваши завершенные проекты и готовые аудиокниги.
          </p>
        </div>
        <Button variant="secondary" onClick={loadBooks} disabled={loading}>
          {loading ? 'Загрузка…' : 'Обновить'}
        </Button>
      </div>

      {error && (
        <div className="mt-4 rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
          {error}
        </div>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-4">
        <button onClick={loadBooks} className="text-sm text-primary dark:text-accent hover:text-text hover:underline transition-colors">
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

      <div className="mt-6">
        {loading ? (
          <div className="text-sm text-textSecondary">Загрузка…</div>
        ) : books.length === 0 ? (
          <div className="rounded-2xl border border-border bg-surfaceSoft p-6 text-center">
            <div className="text-lg mb-2">📚</div>
            <div className="text-sm font-medium text-text mb-1">Пока нет завершенных книг</div>
            <div className="text-xs text-textSecondary mb-4">
              Завершите проект в разделе "Проекты", чтобы он появился здесь
            </div>
            <Link href="/app/projects">
              <Button variant="outline" size="sm">
                Перейти к проектам
              </Button>
            </Link>
          </div>
        ) : (
          <div className="grid gap-6">
            {books.map((book) => {
              if (book.fromApp) {
                const canStartTts = book.status && ['analyzed', 'tts_processing', 'assembling'].includes(book.status);
                const hasAudio = Boolean(book.final_audio_path);
                return (
                  <div key={book.id} className="rounded-2xl border border-border bg-surfaceSoft p-6">
                    <div className="flex flex-col gap-4">
                      <div className="flex items-start justify-between gap-2">
                        <h3 className="text-xl font-semibold text-primary dark:text-text">{book.title}</h3>
                        <div className="flex items-center gap-1">
                          {hasAudio && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleDownloadAppBook(book)}
                              disabled={downloadingId === book.id}
                            >
                              <Download className="h-3.5 w-3.5 mr-1" />
                              {downloadingId === book.id ? 'Скачивание…' : 'Скачать'}
                            </Button>
                          )}
                          {canStartTts && (
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => handleStartTtsAppBook(book.id)}
                              disabled={startingTtsId === book.id}
                            >
                              <Play className="h-3.5 w-3.5 mr-1" />
                              {startingTtsId === book.id ? 'Запуск…' : 'Запустить озвучку'}
                            </Button>
                          )}
                          {expandedDeleteId === book.id ? (
                            <div className="flex items-center gap-1 rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-900/20 overflow-hidden">
                              <button type="button" onClick={() => deleteBook(book.id, book.title, book)} disabled={deletingId === book.id} className="flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-red-600 dark:text-red-400">
                                <Check className="h-3.5 w-3.5" /> Подтвердить
                              </button>
                              <button type="button" onClick={() => setExpandedDeleteId(null)} disabled={deletingId === book.id} className="flex items-center gap-1 border-l border-red-300 dark:border-red-800 px-2 py-1.5 text-xs font-medium text-textSecondary">
                                <X className="h-3.5 w-3.5" /> Отменить
                              </button>
                            </div>
                          ) : (
                            <button type="button" onClick={() => setExpandedDeleteId(book.id)} disabled={deletingId === book.id} className="rounded p-1.5 text-textMuted hover:bg-red-900/20 hover:text-red-400">
                              <Trash2 className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </div>
                      <div className="text-xs text-textSecondary">
                        Статус: {book.status ?? '—'}
                        {typeof book.progress === 'number' && (
                          <> · {book.progress}%{book.total_lines != null ? ` (${book.tts_done ?? 0}/${book.total_lines} строк)` : ''}</>
                        )}
                      </div>
                      {typeof book.progress === 'number' && book.progress < 100 && book.progress >= 0 && (
                        <div className="h-2 w-full overflow-hidden rounded-full bg-surfaceSoft">
                          <div className="h-full bg-gradient-to-r from-accent to-accentWarm transition-all duration-300" style={{ width: `${book.progress}%` }} />
                        </div>
                      )}
                    </div>
                  </div>
                );
              }

              const isEditing = editingBookId === book.id;
              const coverUrl = getCoverUrl(book);

              return (
                <div
                  key={book.id}
                  className="rounded-2xl border border-border bg-surfaceSoft p-6"
                >
                  <div className="grid grid-cols-1 md:grid-cols-[200px_1fr] gap-6">
                    {/* Обложка */}
                    <div className="space-y-2">
                      <div className="relative aspect-[2/3] rounded-lg border border-border bg-surface overflow-hidden">
                        {coverUrl ? (
                          <img
                            src={coverUrl}
                            alt={book.title}
                            className="w-full h-full object-cover"
                          />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center text-textMuted">
                            <ImageIcon className="h-12 w-12" />
                          </div>
                        )}
                        {!isEditing && (
                          <div className="absolute inset-0 bg-black/0 hover:bg-black/20 transition-colors flex items-center justify-center opacity-0 hover:opacity-100">
                            <input
                              ref={(el) => {
                                coverInputRefs.current[book.id] = el;
                              }}
                              type="file"
                              accept="image/jpeg,image/png,image/webp"
                              className="hidden"
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) handleCoverUpload(book.id, file);
                                e.target.value = '';
                              }}
                            />
                            <button
                              type="button"
                              onClick={() => coverInputRefs.current[book.id]?.click()}
                              disabled={uploadingCover === book.id}
                              className="rounded-lg bg-surfaceSoft/90 px-3 py-2 text-sm font-medium text-text hover:bg-surfaceSoft transition-colors"
                            >
                              {uploadingCover === book.id ? 'Загрузка...' : 'Изменить обложку'}
                            </button>
                          </div>
                        )}
                      </div>
                      {uploadingCover === book.id && (
                        <div className="text-xs text-textSecondary text-center">Загрузка обложки...</div>
                      )}
                    </div>

                    {/* Информация о книге */}
                    <div className="space-y-4">
                      {isEditing ? (
                        /* Режим редактирования */
                        <div className="space-y-3">
                          <div>
                            <label className="text-xs font-medium text-text mb-1 block">Название</label>
                            <input
                              type="text"
                              value={editingBook?.title || ''}
                              onChange={(e) => setEditingBook({ ...editingBook, title: e.target.value })}
                              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-primary"
                              placeholder="Название книги"
                            />
                          </div>
                          <div>
                            <label className="text-xs font-medium text-text mb-1 block">Автор</label>
                            <input
                              type="text"
                              value={editingBook?.author || ''}
                              onChange={(e) => setEditingBook({ ...editingBook, author: e.target.value })}
                              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-primary"
                              placeholder="Имя автора"
                            />
                          </div>
                          <div>
                            <label className="text-xs font-medium text-text mb-1 block">Описание</label>
                            <textarea
                              value={editingBook?.description || ''}
                              onChange={(e) => setEditingBook({ ...editingBook, description: e.target.value })}
                              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-primary resize-y min-h-[80px]"
                              placeholder="Описание книги"
                              rows={3}
                            />
                          </div>
                          <div>
                            <label className="text-xs font-medium text-text mb-1 block">Жанр</label>
                            <select
                              value={editingBook?.genre || ''}
                              onChange={(e) => setEditingBook({ ...editingBook, genre: e.target.value || null })}
                              className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-primary"
                            >
                              <option value="">Не выбран</option>
                              {BOOK_GENRES.map((genre) => (
                                <option key={genre} value={genre}>
                                  {genre}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="text-xs font-medium text-text mb-1 block">Серия книг</label>
                            <div className="space-y-2">
                              {!showCreateSeries ? (
                                <>
                                  <select
                                    value={editingBook?.seriesId || ''}
                                    onChange={(e) => {
                                      const selectedSeries = availableSeries.find((s) => s.id === e.target.value);
                                      setEditingBook({
                                        ...editingBook,
                                        seriesId: e.target.value || null,
                                        seriesName: selectedSeries?.name || null,
                                      });
                                    }}
                                    className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-primary"
                                    disabled={loadingSeries}
                                  >
                                    <option value="">Не входит в серию</option>
                                    {availableSeries.map((series) => (
                                      <option key={series.id} value={series.id}>
                                        {series.name} ({series.bookCount} {series.bookCount === 1 ? 'книга' : 'книг'})
                                      </option>
                                    ))}
                                  </select>
                                  <button
                                    type="button"
                                    onClick={() => setShowCreateSeries(true)}
                                    className="text-xs text-primary dark:text-accent hover:underline"
                                  >
                                    + Создать новую серию
                                  </button>
                                </>
                              ) : (
                                <>
                                  <input
                                    type="text"
                                    value={newSeriesName}
                                    onChange={(e) => setNewSeriesName(e.target.value)}
                                    placeholder="Название серии"
                                    className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-primary"
                                  />
                                  <div className="flex items-center gap-2">
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setShowCreateSeries(false);
                                        setNewSeriesName('');
                                      }}
                                      className="text-xs text-textSecondary hover:text-text"
                                    >
                                      Отмена
                                    </button>
                                  </div>
                                </>
                              )}
                              {editingBook?.seriesId && (
                                <div className="mt-2">
                                  <label className="text-xs font-medium text-text mb-1 block">Порядковый номер в серии</label>
                                  <input
                                    type="number"
                                    min="1"
                                    value={editingBook?.seriesOrder || ''}
                                    onChange={(e) => setEditingBook({ ...editingBook, seriesOrder: e.target.value ? parseInt(e.target.value) : null })}
                                    className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text outline-none focus:border-primary"
                                    placeholder="1, 2, 3..."
                                  />
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Button
                              size="sm"
                              onClick={() => saveBook(book.id)}
                              disabled={saving}
                            >
                              <Save className="h-3.5 w-3.5 mr-1.5" />
                              {saving ? 'Сохранение...' : 'Сохранить'}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={cancelEditing}
                              disabled={saving}
                            >
                              <X className="h-3.5 w-3.5 mr-1.5" />
                              Отмена
                            </Button>
                          </div>
                        </div>
                      ) : (
                        /* Режим просмотра */
                        <div className="space-y-3">
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1">
                              <div className="flex items-start gap-2 mb-1">
                                <h3 className="text-xl font-semibold text-primary dark:text-text">{book.title}</h3>
                                {book.seriesName && (
                                  <span className="text-xs text-textSecondary bg-surfaceSoft px-2 py-0.5 rounded">
                                    {book.seriesName}
                                    {book.seriesOrder && ` #${book.seriesOrder}`}
                                  </span>
                                )}
                              </div>
                              {book.author && (
                                <div className="text-sm text-textSecondary mb-1">Автор: {book.author}</div>
                              )}
                              {book.genre && (
                                <div className="text-sm text-textSecondary mb-1">
                                  <span className="font-medium">Жанр:</span> {book.genre}
                                </div>
                              )}
                              {book.description && (
                                <div className="text-sm text-textSecondary mb-2">{book.description}</div>
                              )}
                              <div className="text-xs text-textMuted">
                                {book.language} · Завершена {book.completedAt ? new Date(book.completedAt).toLocaleDateString() : new Date(book.updatedAt).toLocaleDateString()}
                              </div>
                            </div>
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                onClick={() => startEditing(book)}
                                className="rounded p-1.5 text-textMuted hover:bg-surfaceSoft hover:text-text transition-colors"
                                aria-label="Редактировать"
                              >
                                <Pencil className="h-4 w-4" />
                              </button>
                              {expandedDeleteId === book.id ? (
                                <div className="flex items-center gap-1 rounded-lg border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-900/20 overflow-hidden">
                                  <button
                                    type="button"
                                    onClick={() => deleteBook(book.id, book.title, book)}
                                    disabled={deletingId === book.id}
                                    className="flex items-center gap-1 px-2 py-1.5 text-xs font-medium text-red-600 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/30 disabled:opacity-50"
                                    aria-label="Подтвердить удаление"
                                  >
                                    <Check className="h-3.5 w-3.5" />
                                    Подтвердить
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => setExpandedDeleteId(null)}
                                    disabled={deletingId === book.id}
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
                                  onClick={() => setExpandedDeleteId(book.id)}
                                  disabled={deletingId === book.id}
                                  className="rounded p-1.5 text-textMuted hover:bg-red-900/20 hover:text-red-400 disabled:opacity-50 transition-colors"
                                  aria-label="Удалить книгу"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Аудио плеер — финализированная (audiobookFolder) / appBookId (App API) / book.audio (Nest) */}
                          <div className="space-y-2">
                            {(book.audiobookFolder || book.appBookId) && isAppApiEnabled() ? (
                              <>
                                <div className="flex items-center gap-2 mb-2">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleDownloadAppBook(book)}
                                    disabled={downloadingId === book.id}
                                  >
                                    <Download className="h-3.5 w-3.5 mr-1" />
                                    {downloadingId === book.id ? 'Скачивание…' : 'Скачать'}
                                  </Button>
                                  {!appBookPlaybackUrls[book.id] && (
                                    <Button
                                      variant="secondary"
                                      size="sm"
                                      onClick={() => loadAppBookPlayback(book.id, book)}
                                    >
                                      <Play className="h-3.5 w-3.5 mr-1" />
                                      Прослушать
                                    </Button>
                                  )}
                                </div>
                                {appBookPlaybackUrls[book.id] && (
                                  <audio controls className="w-full" src={appBookPlaybackUrls[book.id]} />
                                )}
                              </>
                            ) : book.audio?.streamUrl ? (
                              <>
                                <div className="flex items-center gap-4 text-xs text-textSecondary">
                                  {book.audio.durationSeconds && (
                                    <span>Длительность: {formatDuration(book.audio.durationSeconds)}</span>
                                  )}
                                  {book.audio.format && (
                                    <span>Формат: {book.audio.format.toUpperCase()}</span>
                                  )}
                                </div>
                                <audio
                                  controls
                                  className="w-full"
                                  src={getAudioUrl(book.audio.streamUrl)}
                                />
                              </>
                            ) : (
                              <>
                                <div className="text-xs text-textSecondary mb-2">
                                  Аудиокнига еще не сгенерирована
                                </div>
                                <div className="w-full h-12 rounded-lg border border-border bg-surface flex items-center justify-center">
                                  <div className="flex items-center gap-2 text-textMuted">
                                    <div className="w-8 h-8 rounded-full border-2 border-border flex items-center justify-center">
                                      <div className="w-0 h-0 border-l-[6px] border-l-textMuted border-y-[4px] border-y-transparent ml-0.5" />
                                    </div>
                                    <span className="text-sm">Аудио будет доступно после генерации</span>
                                  </div>
                                </div>
                              </>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Корзина удаленных книг */}
      {showTrash && (
        <div className="mt-6 rounded-2xl border border-border bg-surfaceSoft p-4">
          <div className="mb-2 text-sm font-medium text-text">Корзина</div>
          <p className="mb-3 text-xs text-textSecondary">
            Удалённые книги хранятся 7 дней. Восстановите книгу до истечения срока.
          </p>
          {trashLoading ? (
            <div className="py-4 text-sm text-textMuted">Загрузка…</div>
          ) : trash.length === 0 ? (
            <div className="py-4 text-center text-sm text-textMuted">В корзине пусто.</div>
          ) : (
            <ul className="space-y-2">
              {trash.map((book) => (
                <li
                  key={book.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border bg-surface px-3 py-2"
                >
                  <div className="min-w-0">
                    <span className="font-medium text-text">{book.title}</span>
                    <span className="ml-2 text-xs text-textMuted">
                      {book.language} · {formatTrashRemaining(book.deletedAt)}
                    </span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => restoreBook(book.id)}
                    disabled={restoringId === book.id}
                  >
                    {restoringId === book.id ? 'Восстановление…' : 'Восстановить'}
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
