import { useTranslation } from 'react-i18next'
import { saveLanguage } from '@/i18n/config'

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation()

  function switchLanguage(lang: string) {
    void i18n.changeLanguage(lang)
    saveLanguage(lang)
  }

  return (
    <div className="language-switcher" role="group" aria-label={t('app.language')}>
      <button
        type="button"
        className={`language-switcher__button ${i18n.language === 'bg' ? 'language-switcher__button--active' : ''}`}
        onClick={() => switchLanguage('bg')}
        aria-pressed={i18n.language === 'bg'}
      >
        BG
      </button>
      <button
        type="button"
        className={`language-switcher__button ${i18n.language === 'en' ? 'language-switcher__button--active' : ''}`}
        onClick={() => switchLanguage('en')}
        aria-pressed={i18n.language === 'en'}
      >
        EN
      </button>
    </div>
  )
}
