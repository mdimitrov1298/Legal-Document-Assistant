import { useTranslation } from 'react-i18next'

export function Disclaimer() {
  const { t } = useTranslation()
  return (
    <footer className="disclaimer">
      <p>{t('disclaimer.line1')}</p>
      <p>{t('disclaimer.line2')}</p>
    </footer>
  )
}
