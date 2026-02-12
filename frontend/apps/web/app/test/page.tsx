'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { Upload, Play, Pause, Volume2, VolumeX, Loader2, CheckCircle2, Clock, AlertCircle } from 'lucide-react';
import { Button } from '../../components/ui';

// API calls go through Next.js proxy (see next.config.mjs rewrites)
const API_BASE = '';

type BookStatus = {
  stage: string;
  progress: number;
  total_lines: number;
  tts_done: number;
};

type Chapter = {
  chapter_id: number;
  title: string;
  audio_url: string | null;
  status: 'pending' | 'processing' | 'ready';
  lines_done: number;
  lines_total: number;
};

type LineInfo = {
  id: string;
  idx: number;
  text: string;
  speaker: string;
  status: string;
  audio_url: string | null;
  chapter_id: number;
};

export default function TestPage() {
  const [file, setFile] = useState<File | null>(null);
  const [bookId, setBookId] = useState<string | null>(null);
  const [status, setStatus] = useState<BookStatus | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [lines, setLines] = useState<LineInfo[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Audio player state
  const [currentChapter, setCurrentChapter] = useState<number | null>(null);
  const [currentLine, setCurrentLine] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  
  const audioRef = useRef<HTMLAudioElement>(null);
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Polling for status updates
  const pollStatus = useCallback(async () => {
    if (!bookId) return;
    
    try {
      const [statusRes, chaptersRes, linesRes] = await Promise.all([
        fetch(`${API_BASE}/test/${bookId}/status`),
        fetch(`${API_BASE}/test/${bookId}/chapters`),
        fetch(`${API_BASE}/test/${bookId}/lines`),
      ]);
      
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        setStatus(statusData);
        
        // Stop polling when completed or error
        if (statusData.stage === 'completed' || statusData.stage === 'error') {
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
            pollIntervalRef.current = null;
          }
        }
      }
      
      if (chaptersRes.ok) {
        const chaptersData = await chaptersRes.json();
        setChapters(chaptersData.chapters || []);
      }
      
      if (linesRes.ok) {
        const linesData = await linesRes.json();
        setLines(linesData.lines || []);
      }
    } catch (e) {
      console.error('Polling error:', e);
    }
  }, [bookId]);

  useEffect(() => {
    if (bookId && !pollIntervalRef.current) {
      pollStatus();
      pollIntervalRef.current = setInterval(pollStatus, 3000);
    }
    
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [bookId, pollStatus]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    
    setUploading(true);
    setError(null);
    
    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const res = await fetch(`${API_BASE}/test/upload`, {
        method: 'POST',
        body: formData,
      });
      
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Upload failed: ${res.status}`);
      }
      
      const data = await res.json();
      setBookId(data.id);
      setStatus({ stage: data.status, progress: 0, total_lines: 0, tts_done: 0 });
    } catch (e: any) {
      setError(e.message || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const playChapter = (chapter: Chapter) => {
    if (!chapter.audio_url) return;
    
    setCurrentChapter(chapter.chapter_id);
    setCurrentLine(null);
    
    if (audioRef.current) {
      audioRef.current.src = `${API_BASE}${chapter.audio_url}`;
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  const playLine = (line: LineInfo) => {
    if (!line.audio_url) return;
    
    setCurrentLine(line.id);
    setCurrentChapter(null);
    
    if (audioRef.current) {
      audioRef.current.src = `${API_BASE}${line.audio_url}`;
      audioRef.current.play();
      setIsPlaying(true);
    }
  };

  const togglePlay = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const vol = parseFloat(e.target.value);
    setVolume(vol);
    if (audioRef.current) {
      audioRef.current.volume = vol;
    }
    setIsMuted(vol === 0);
  };

  const toggleMute = () => {
    if (audioRef.current) {
      audioRef.current.muted = !isMuted;
      setIsMuted(!isMuted);
    }
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const getStageLabel = (stage: string) => {
    const labels: Record<string, string> = {
      stage0: 'Загрузка файла',
      stage1: 'Разбор текста',
      stage2: 'Анализ персонажей',
      stage3: 'Подготовка к озвучке',
      stage4: 'Озвучивание',
      stage5: 'Сборка аудио',
      completed: 'Готово',
      error: 'Ошибка',
    };
    return labels[stage] || stage;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'ready':
      case 'tts_done':
      case 'assembled':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'processing':
      case 'tts_pending':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />;
      case 'error':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-zinc-400" />;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-50 to-zinc-100">
      <div className="mx-auto max-w-4xl px-6 py-12">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-[var(--color-primary)]">
            Тест озвучки книги
          </h1>
          <p className="mt-2 text-zinc-600">
            Загрузите текстовый файл и получите озвученную аудиокнигу
          </p>
        </div>

        {/* Upload Section */}
        {!bookId && (
          <div className="rounded-2xl border-2 border-dashed border-zinc-300 bg-white p-8 text-center transition hover:border-[var(--color-secondary)]">
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.epub,.fb2"
              onChange={handleFileChange}
              className="hidden"
            />
            
            <div 
              className="cursor-pointer"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="mx-auto h-12 w-12 text-zinc-400" />
              <p className="mt-4 text-lg font-medium text-zinc-700">
                {file ? file.name : 'Выберите файл для озвучки'}
              </p>
              <p className="mt-1 text-sm text-zinc-500">
                Поддерживаются форматы: TXT, EPUB, FB2
              </p>
            </div>

            {file && (
              <Button
                onClick={handleUpload}
                disabled={uploading}
                className="mt-6 !bg-[var(--color-accent)] !text-[var(--color-primary)] hover:!opacity-90"
              >
                {uploading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Загрузка...
                  </>
                ) : (
                  'Отправить на озвучку'
                )}
              </Button>
            )}
          </div>
        )}

        {error && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
            {error}
          </div>
        )}

        {/* Status Section */}
        {status && (
          <div className="mt-8 rounded-2xl bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-[var(--color-primary)]">
                  Статус обработки
                </h2>
                <p className="text-sm text-zinc-600">{getStageLabel(status.stage)}</p>
              </div>
              <div className="text-right">
                <div className="text-2xl font-bold text-[var(--color-secondary)]">
                  {status.progress}%
                </div>
                <div className="text-xs text-zinc-500">
                  {status.tts_done} / {status.total_lines} строк
                </div>
              </div>
            </div>
            
            {/* Progress bar */}
            <div className="mt-4 h-3 overflow-hidden rounded-full bg-zinc-200">
              <div
                className="h-full rounded-full bg-gradient-to-r from-[var(--color-secondary)] to-[var(--color-accent)] transition-all duration-500"
                style={{ width: `${status.progress}%` }}
              />
            </div>

            {/* Stage indicators */}
            <div className="mt-4 flex justify-between text-xs text-zinc-500">
              {['stage0', 'stage1', 'stage2', 'stage3', 'stage4', 'stage5'].map((stage, idx) => (
                <div
                  key={stage}
                  className={`flex items-center gap-1 ${
                    status.stage === stage
                      ? 'font-medium text-[var(--color-secondary)]'
                      : status.stage === 'completed' || 
                        ['stage0', 'stage1', 'stage2', 'stage3', 'stage4', 'stage5'].indexOf(status.stage) > idx
                      ? 'text-green-600'
                      : ''
                  }`}
                >
                  <span className={`inline-block h-2 w-2 rounded-full ${
                    status.stage === stage
                      ? 'bg-[var(--color-secondary)] animate-pulse'
                      : status.stage === 'completed' || 
                        ['stage0', 'stage1', 'stage2', 'stage3', 'stage4', 'stage5'].indexOf(status.stage) > idx
                      ? 'bg-green-500'
                      : 'bg-zinc-300'
                  }`} />
                  {idx}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Audio Player */}
        {(currentChapter !== null || currentLine !== null) && (
          <div className="mt-6 rounded-2xl bg-[var(--color-primary)] p-4 text-white shadow-lg">
            <audio
              ref={audioRef}
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onEnded={() => setIsPlaying(false)}
            />
            
            <div className="flex items-center gap-4">
              <button
                onClick={togglePlay}
                className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-accent)] text-[var(--color-primary)] transition hover:opacity-90"
              >
                {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5 ml-0.5" />}
              </button>
              
              <div className="flex-1">
                <div className="mb-1 text-sm font-medium">
                  {currentChapter !== null
                    ? chapters.find(c => c.chapter_id === currentChapter)?.title || `Глава ${currentChapter}`
                    : lines.find(l => l.id === currentLine)?.text.slice(0, 50) + '...'
                  }
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-300">{formatTime(currentTime)}</span>
                  <input
                    type="range"
                    min={0}
                    max={duration || 100}
                    value={currentTime}
                    onChange={handleSeek}
                    className="flex-1 h-1 cursor-pointer appearance-none rounded-full bg-zinc-600 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white"
                  />
                  <span className="text-xs text-zinc-300">{formatTime(duration)}</span>
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                <button onClick={toggleMute} className="text-zinc-300 hover:text-white">
                  {isMuted ? <VolumeX className="h-5 w-5" /> : <Volume2 className="h-5 w-5" />}
                </button>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.1}
                  value={isMuted ? 0 : volume}
                  onChange={handleVolumeChange}
                  className="w-20 h-1 cursor-pointer appearance-none rounded-full bg-zinc-600 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white"
                />
              </div>
            </div>
          </div>
        )}

        {/* Chapters List */}
        {chapters.length > 0 && (
          <div className="mt-8">
            <h2 className="mb-4 text-xl font-semibold text-[var(--color-primary)]">
              Главы
            </h2>
            <div className="space-y-2">
              {chapters.map((chapter) => (
                <div
                  key={chapter.chapter_id}
                  className={`flex items-center justify-between rounded-xl border-2 p-4 transition ${
                    currentChapter === chapter.chapter_id
                      ? 'border-[var(--color-secondary)] bg-[var(--color-secondary)]/5'
                      : 'border-zinc-200 bg-white hover:border-zinc-300'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    {getStatusIcon(chapter.status)}
                    <div>
                      <div className="font-medium text-[var(--color-primary)]">{chapter.title}</div>
                      <div className="text-xs text-zinc-500">
                        {chapter.lines_done} / {chapter.lines_total} строк озвучено
                      </div>
                    </div>
                  </div>
                  
                  {chapter.status === 'ready' && (
                    <button
                      onClick={() => playChapter(chapter)}
                      className="flex items-center gap-2 rounded-lg bg-[var(--color-secondary)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90"
                    >
                      <Play className="h-4 w-4" />
                      Слушать
                    </button>
                  )}
                  
                  {chapter.status === 'processing' && (
                    <div className="flex items-center gap-2 text-sm text-zinc-500">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Обработка...
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Lines List (collapsible by chapter) */}
        {lines.length > 0 && (
          <div className="mt-8">
            <h2 className="mb-4 text-xl font-semibold text-[var(--color-primary)]">
              Строки ({lines.filter(l => l.status === 'tts_done' || l.status === 'assembled').length} / {lines.length} готово)
            </h2>
            <div className="max-h-96 overflow-y-auto rounded-xl border border-zinc-200 bg-white">
              {lines.map((line) => (
                <div
                  key={line.id}
                  className={`flex items-start gap-3 border-b border-zinc-100 p-3 last:border-b-0 ${
                    currentLine === line.id ? 'bg-[var(--color-secondary)]/5' : ''
                  }`}
                >
                  <div className="mt-0.5">{getStatusIcon(line.status)}</div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-[var(--color-secondary)]">
                        {line.speaker}
                      </span>
                      <span className="text-xs text-zinc-400">#{line.idx}</span>
                    </div>
                    <p className="mt-0.5 text-sm text-zinc-700 line-clamp-2">{line.text}</p>
                  </div>
                  {line.audio_url && (
                    <button
                      onClick={() => playLine(line)}
                      className="shrink-0 rounded p-1.5 text-[var(--color-secondary)] hover:bg-[var(--color-secondary)]/10"
                    >
                      <Play className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Reset button */}
        {bookId && (
          <div className="mt-8 text-center">
            <button
              onClick={() => {
                setBookId(null);
                setStatus(null);
                setChapters([]);
                setLines([]);
                setFile(null);
                setCurrentChapter(null);
                setCurrentLine(null);
                setIsPlaying(false);
                if (pollIntervalRef.current) {
                  clearInterval(pollIntervalRef.current);
                  pollIntervalRef.current = null;
                }
              }}
              className="text-sm text-zinc-500 hover:text-[var(--color-secondary)] hover:underline"
            >
              Загрузить другую книгу
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
