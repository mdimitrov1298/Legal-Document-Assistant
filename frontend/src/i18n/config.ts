import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { bg } from './locales/bg'
import { en } from './locales/en'

const STORAGE_KEY = 'legalAssistantLanguage'
const DEFAULT_LANGUAGE = 'bg'

// Get stored language or default
function getInitialLanguage(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_LANGUAGE
  } catch {
    return DEFAULT_LANGUAGE
  }
}

// Store language preference
export function saveLanguage(lang: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // Ignore localStorage errors
  }
}

void i18n.use(initReactI18next).init({
  resources: {
    bg,
    en,
  },
  lng: getInitialLanguage(),
  fallbackLng: 'bg',
  interpolation: {
    escapeValue: false,
  },
})

export default i18n
