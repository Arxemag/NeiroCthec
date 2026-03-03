/**
 * Утилиты для работы с темой
 */

export type Theme = 'dark' | 'light';

const THEME_STORAGE_KEY = 'neurochtec-theme';

/**
 * Получает сохраненную тему из localStorage
 */
export function getStoredTheme(): Theme | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === 'light' || stored === 'dark') {
      return stored as Theme;
    }
  } catch {
    // Игнорируем ошибки доступа к localStorage
  }
  return null;
}

/**
 * Сохраняет тему в localStorage
 */
export function saveTheme(theme: Theme) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Игнорируем ошибки доступа к localStorage
  }
}

/**
 * Устанавливает тему для документа и сохраняет её
 */
export function setTheme(theme: Theme) {
  if (typeof window === 'undefined') return;
  const html = document.documentElement;
  if (theme === 'light') {
    html.classList.add('light');
    html.classList.remove('dark');
  } else {
    html.classList.add('dark');
    html.classList.remove('light');
  }
  saveTheme(theme);
}

/**
 * Получает текущую тему из DOM или localStorage
 */
export function getTheme(): Theme {
  if (typeof window === 'undefined') return 'dark';
  
  // Сначала проверяем сохраненную тему
  const stored = getStoredTheme();
  if (stored) {
    return stored;
  }
  
  // Если сохраненной темы нет, проверяем DOM
  return document.documentElement.classList.contains('light') ? 'light' : 'dark';
}

/**
 * Инициализирует тему при загрузке страницы
 */
export function initTheme() {
  if (typeof window === 'undefined') return;
  
  const stored = getStoredTheme();
  if (stored) {
    setTheme(stored);
  } else {
    // Если темы нет в localStorage, используем значение из HTML класса
    const current = document.documentElement.classList.contains('light') ? 'light' : 'dark';
    saveTheme(current);
  }
}

/**
 * Переключает тему
 */
export function toggleTheme() {
  const current = getTheme();
  const newTheme = current === 'dark' ? 'light' : 'dark';
  setTheme(newTheme);
}
