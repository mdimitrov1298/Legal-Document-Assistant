import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { bg } from './locales/bg'
import { en } from './locales/en'

const STORAGE_KEY = 'legalAssistantLanguage'
const DEFAULT_LANGUAGE = 'bg'

function getInitialLanguage(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_LANGUAGE
  } catch {
    return DEFAULT_LANGUAGE
  }
}

export function saveLanguage(lang: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // Ignore localStorage errors
  }
}

function applyDocumentMeta(lang: string): void {
  if (typeof document === 'undefined') return
  document.documentElement.lang = lang
  document.title = i18n.t('app.title')
}

void i18n
  .use(initReactI18next)
  .init({
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
  .then(() => {
    applyDocumentMeta(i18n.language)
  })

i18n.on('languageChanged', (lng) => {
  applyDocumentMeta(lng)
})

export default i18n
