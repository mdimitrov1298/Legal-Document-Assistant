import { useTranslation } from 'react-i18next'

interface LanguageBadgeProps {
  language: string | undefined
}

function badgeLabel(lang: string | undefined): string {
  if (!lang) return '?'
  const normalized = lang.toLowerCase()
  if (normalized === 'bg') return 'BG'
  if (normalized === 'en') return 'EN'
  return '?'
}

function badgeClass(lang: string | undefined): string {
  const normalized = lang?.toLowerCase()
  if (normalized === 'bg') return 'lang-badge lang-badge--bg'
  if (normalized === 'en') return 'lang-badge lang-badge--en'
  return 'lang-badge lang-badge--other'
}

export function LanguageBadge({ language }: LanguageBadgeProps) {
  const { t } = useTranslation()
  const langLabel = language ?? t('documents.languageUnknown')
  
  return (
    <span className={badgeClass(language)} title={t('documents.languageTitle', { language: langLabel })}>
      {badgeLabel(language)}
    </span>
  )
}
