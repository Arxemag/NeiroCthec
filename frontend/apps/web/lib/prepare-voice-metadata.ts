/**
 * Утилита для подготовки метаданных голосов из файлов в папке audio/
 * 
 * Использование:
 * 1. Поместите аудио файлы в public/cache/voices/audio/ с именами:
 *    - narrator_1.mp3, narrator_2.mp3 (для дикторов)
 *    - male_1.mp3, male_2.mp3 (для мужских голосов)
 *    - female_1.mp3, female_2.mp3 (для женских голосов)
 * 
 * 2. Запустите эту функцию для генерации метаданных
 */

export interface VoiceFileInfo {
  fileName: string;
  role: 'narrator' | 'male' | 'female';
  index: number;
  extension: string;
}

/**
 * Парсит имя файла и извлекает информацию о голосе
 */
export function parseVoiceFileName(fileName: string): VoiceFileInfo | null {
  // Формат: {role}_{index}.{ext}
  // Примеры: narrator_1.mp3, male_2.wav, female_1.ogg
  
  const match = fileName.match(/^(narrator|male|female)_(\d+)\.(mp3|wav|ogg|m4a)$/i);
  if (!match) {
    return null;
  }

  const [, roleStr, indexStr, ext] = match;
  const role = roleStr.toLowerCase() as 'narrator' | 'male' | 'female';
  const index = parseInt(indexStr, 10);

  return {
    fileName,
    role,
    index,
    extension: ext.toLowerCase(),
  };
}

/**
 * Генерирует метаданные для голоса на основе имени файла
 */
export function generateVoiceMetadata(fileInfo: VoiceFileInfo): {
  id: string;
  name: string;
  description: string;
  gender: 'male' | 'female' | 'neutral';
  ageRange: 'adult';
  language: 'ru';
  audioFile: string;
  previewText: string;
  tags: string[];
} {
  const roleNames = {
    narrator: 'Диктор',
    male: 'Мужской голос',
    female: 'Женский голос',
  };

  const roleDescriptions = {
    narrator: 'Профессиональный дикторский голос для повествования',
    male: 'Мужской голос актера',
    female: 'Женский голос актера',
  };

  const roleTags = {
    narrator: ['диктор', 'повествование'],
    male: ['мужской', 'актер'],
    female: ['женский', 'актер'],
  };

  const name = `${roleNames[fileInfo.role]} ${fileInfo.index}`;
  const gender = fileInfo.role === 'narrator' ? 'neutral' : fileInfo.role;
  
  return {
    id: `${fileInfo.role}-${fileInfo.index}`,
    name,
    description: roleDescriptions[fileInfo.role],
    gender,
    ageRange: 'adult',
    language: 'ru',
    audioFile: `/cache/voices/audio/${fileInfo.fileName}`,
    previewText: fileInfo.role === 'narrator' 
      ? 'Это пример дикторского голоса для повествования.'
      : fileInfo.role === 'male'
      ? 'Привет, это пример мужского голоса актера.'
      : 'Здравствуйте, это пример женского голоса актера.',
    tags: roleTags[fileInfo.role],
  };
}

/**
 * Сканирует папку audio и генерирует метаданные для всех найденных файлов
 * 
 * ВАЖНО: Эта функция работает только в браузере и требует, чтобы файлы были доступны
 * через файловую систему или через API для сканирования директории.
 * 
 * Для использования:
 * 1. Вручную добавьте файлы в public/cache/voices/audio/
 * 2. Используйте эту функцию для генерации JSON метаданных
 * 3. Скопируйте результат в voice-metadata.json
 */
export async function scanAudioFolderAndGenerateMetadata(): Promise<{
  voices: ReturnType<typeof generateVoiceMetadata>[];
  metadata: {
    version: string;
    lastSync: string | null;
    totalVoices: number;
  };
}> {
  // В браузере мы не можем сканировать файловую систему напрямую
  // Эта функция возвращает структуру для ручного заполнения
  
  // В реальности нужно будет использовать API endpoint для сканирования
  // или вручную указать список файлов
  
  return {
    voices: [],
    metadata: {
      version: '1.0.0',
      lastSync: null,
      totalVoices: 0,
    },
  };
}

/**
 * Пример использования для ручного создания метаданных
 * 
 * Скопируйте этот код в консоль браузера после загрузки страницы:
 */
export const exampleUsage = `
// Пример использования в консоли браузера:

// 1. Список файлов (замените на реальные имена файлов из папки audio/)
const fileNames = [
  'narrator_1.mp3',
  'narrator_2.mp3',
  'male_1.mp3',
  'male_2.mp3',
  'female_1.mp3',
  'female_2.mp3',
];

// 2. Генерация метаданных
const voices = fileNames
  .map(fileName => parseVoiceFileName(fileName))
  .filter(Boolean)
  .map(fileInfo => generateVoiceMetadata(fileInfo));

// 3. Создание полной структуры
const metadata = {
  voices,
  metadata: {
    version: '1.0.0',
    lastSync: new Date().toISOString(),
    totalVoices: voices.length,
  },
};

// 4. Вывод JSON для копирования
console.log(JSON.stringify(metadata, null, 2));
`;
