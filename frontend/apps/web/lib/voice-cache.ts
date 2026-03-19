/**
 * Утилиты для работы с кэшем голосов актеров
 */

export interface VoiceMetadata {
  id: string;
  name: string;
  description: string;
  gender: 'male' | 'female';
  ageRange: 'child' | 'teen' | 'adult' | 'elder';
  language: string;
  audioFile: string;
  previewText: string;
  tags: string[];
  createdAt: string;
  updatedAt: string;
}

export interface VoiceCacheData {
  voices: VoiceMetadata[];
  metadata: {
    version: string;
    lastSync: string | null;
    totalVoices: number;
  };
}

/**
 * Загружает метаданные голосов из кэша
 */
export async function loadVoiceMetadata(): Promise<VoiceCacheData | null> {
  try {
    // В Next.js файлы из public доступны напрямую через корневой путь
    const response = await fetch('/cache/voices/meta/voice-metadata.json');
    if (!response.ok) {
      return null;
    }
    return await response.json();
  } catch (error) {
    console.error('Failed to load voice metadata:', error);
    return null;
  }
}

/**
 * Получает голос по ID
 */
export async function getVoiceById(id: string): Promise<VoiceMetadata | null> {
  const data = await loadVoiceMetadata();
  if (!data) {
    return null;
  }
  return data.voices.find((voice) => voice.id === id) || null;
}

/**
 * Получает все голоса
 */
export async function getAllVoices(): Promise<VoiceMetadata[]> {
  const data = await loadVoiceMetadata();
  return data?.voices || [];
}

/**
 * Получает голоса по фильтрам
 */
export async function getVoicesByFilter(filters: {
  gender?: 'male' | 'female';
  ageRange?: 'child' | 'teen' | 'adult' | 'elder';
  language?: string;
  tags?: string[];
}): Promise<VoiceMetadata[]> {
  const voices = await getAllVoices();
  
  return voices.filter((voice) => {
    if (filters.gender && voice.gender !== filters.gender) {
      return false;
    }
    if (filters.ageRange && voice.ageRange !== filters.ageRange) {
      return false;
    }
    if (filters.language && voice.language !== filters.language) {
      return false;
    }
    if (filters.tags && filters.tags.length > 0) {
      const hasAllTags = filters.tags.every((tag) => voice.tags.includes(tag));
      if (!hasAllTags) {
        return false;
      }
    }
    return true;
  });
}

/**
 * Получает URL аудио файла голоса
 */
export function getVoiceAudioUrl(audioFile: string): string {
  // Если путь уже полный URL, возвращаем как есть
  if (audioFile.startsWith('http://') || audioFile.startsWith('https://')) {
    return audioFile;
  }
  // Если путь уже начинается с /cache, возвращаем как есть
  if (audioFile.startsWith('/cache/')) {
    return audioFile;
  }
  // Иначе добавляем базовый путь к файлу в public/cache
  return audioFile.startsWith('/') 
    ? `/cache/voices/audio${audioFile}` 
    : `/cache/voices/audio/${audioFile}`;
}
