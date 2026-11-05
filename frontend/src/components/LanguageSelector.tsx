import { useId } from 'react'
import { useTranslation } from 'react-i18next'
import type { AnswerLanguage } from '@/api/types'

interface LanguageSelectorProps {
  value: AnswerLanguage
  onChange: (lang: AnswerLanguage) => void
  disabled?: boolean
}

export function LanguageSelector({ value, onChange, disabled }: LanguageSelectorProps) {
  const { t } = useTranslation()
  const selectId = useId()
  
  return (
    <div className="language-selector">
      <label htmlFor={selectId} className="language-selector__label">
        {t('answerLanguage.label')}
      </label>
      <select
        id={selectId}
        className="language-selector__select"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as AnswerLanguage)}
      >
        <option value="auto">{t('answerLanguage.auto')}</option>
        <option value="bg">{t('answerLanguage.bg')}</option>
        <option value="en">{t('answerLanguage.en')}</option>
      </select>
    </div>
  )
}
