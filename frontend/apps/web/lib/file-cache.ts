/**
 * Утилиты для кэширования файлов проектов
 */

export interface CachedFile {
  projectId: string;
  fileName: string;
  fileContent: string;
  fileType: string;
  uploadedAt: string;
  fileSize: number;
}

const CACHE_KEY_PREFIX = 'project_file_cache_';
const CACHE_METADATA_KEY = 'project_files_metadata';

/**
 * Получает ключ для кэша файла проекта
 */
function getCacheKey(projectId: string): string {
  return `${CACHE_KEY_PREFIX}${projectId}`;
}

/**
 * Сохраняет файл в кэш
 */
export async function cacheProjectFile(
  projectId: string,
  file: File
): Promise<void> {
  try {
    const fileContent = await file.text();
    const cachedFile: CachedFile = {
      projectId,
      fileName: file.name,
      fileContent,
      fileType: file.type || (file.name.toLowerCase().endsWith('.fb2') ? 'application/xml' : file.name.toLowerCase().endsWith('.epub') ? 'application/epub+zip' : file.name.toLowerCase().endsWith('.mobi') ? 'application/x-mobipocket-ebook' : 'text/plain'),
      uploadedAt: new Date().toISOString(),
      fileSize: file.size,
    };

    // Сохраняем файл в localStorage
    const cacheKey = getCacheKey(projectId);
    localStorage.setItem(cacheKey, JSON.stringify(cachedFile));

    // Обновляем метаданные
    updateMetadata(projectId, cachedFile);

    console.log(`File cached for project ${projectId}:`, file.name);
  } catch (error) {
    console.error('Failed to cache file:', error);
    throw error;
  }
}

/**
 * Получает файл из кэша
 */
export function getCachedFile(projectId: string): CachedFile | null {
  try {
    const cacheKey = getCacheKey(projectId);
    const cached = localStorage.getItem(cacheKey);
    if (!cached) {
      return null;
    }
    return JSON.parse(cached) as CachedFile;
  } catch (error) {
    console.error('Failed to get cached file:', error);
    return null;
  }
}

/**
 * Удаляет файл из кэша
 */
export function removeCachedFile(projectId: string): void {
  try {
    const cacheKey = getCacheKey(projectId);
    localStorage.removeItem(cacheKey);
    removeFromMetadata(projectId);
    console.log(`Cached file removed for project ${projectId}`);
  } catch (error) {
    console.error('Failed to remove cached file:', error);
  }
}

/**
 * Проверяет, есть ли файл в кэше
 */
export function hasCachedFile(projectId: string): boolean {
  return getCachedFile(projectId) !== null;
}

/**
 * Создает File объект из кэшированного файла
 */
export function createFileFromCache(cachedFile: CachedFile): File {
  const blob = new Blob([cachedFile.fileContent], { type: cachedFile.fileType });
  return new File([blob], cachedFile.fileName, { type: cachedFile.fileType });
}

/**
 * Обновляет метаданные кэша
 */
function updateMetadata(projectId: string, cachedFile: CachedFile): void {
  try {
    const metadata = getMetadata();
    const existingIndex = metadata.findIndex((m) => m.projectId === projectId);
    
    const entry = {
      projectId,
      fileName: cachedFile.fileName,
      uploadedAt: cachedFile.uploadedAt,
      fileSize: cachedFile.fileSize,
    };

    if (existingIndex >= 0) {
      metadata[existingIndex] = entry;
    } else {
      metadata.push(entry);
    }

    localStorage.setItem(CACHE_METADATA_KEY, JSON.stringify(metadata));
  } catch (error) {
    console.error('Failed to update metadata:', error);
  }
}

/**
 * Удаляет запись из метаданных
 */
function removeFromMetadata(projectId: string): void {
  try {
    const metadata = getMetadata();
    const filtered = metadata.filter((m) => m.projectId !== projectId);
    localStorage.setItem(CACHE_METADATA_KEY, JSON.stringify(filtered));
  } catch (error) {
    console.error('Failed to remove from metadata:', error);
  }
}

/**
 * Получает метаданные всех закэшированных файлов
 */
function getMetadata(): Array<{
  projectId: string;
  fileName: string;
  uploadedAt: string;
  fileSize: number;
}> {
  try {
    const metadata = localStorage.getItem(CACHE_METADATA_KEY);
    return metadata ? JSON.parse(metadata) : [];
  } catch (error) {
    console.error('Failed to get metadata:', error);
    return [];
  }
}

/**
 * Очищает весь кэш файлов (для отладки или очистки)
 */
export function clearAllCachedFiles(): void {
  try {
    const metadata = getMetadata();
    metadata.forEach((entry) => {
      const cacheKey = getCacheKey(entry.projectId);
      localStorage.removeItem(cacheKey);
    });
    localStorage.removeItem(CACHE_METADATA_KEY);
    console.log('All cached files cleared');
  } catch (error) {
    console.error('Failed to clear cache:', error);
  }
}

/**
 * Получает размер кэша в байтах
 */
export function getCacheSize(): number {
  try {
    const metadata = getMetadata();
    return metadata.reduce((total, entry) => total + entry.fileSize, 0);
  } catch (error) {
    console.error('Failed to get cache size:', error);
    return 0;
  }
}
