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
  return (
    <span className={badgeClass(language)} title={`Език на документа: ${language ?? 'неизвестен'}`}>
      {badgeLabel(language)}
    </span>
  )
}
