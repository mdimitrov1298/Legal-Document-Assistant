import { useId } from 'react'
import type { AnswerLanguage } from '@/api/types'

interface LanguageSelectorProps {
  value: AnswerLanguage
  onChange: (lang: AnswerLanguage) => void
  disabled?: boolean
}

const OPTIONS: { value: AnswerLanguage; label: string }[] = [
  { value: 'auto', label: 'Автоматично' },
  { value: 'bg', label: 'Български' },
  { value: 'en', label: 'English' },
]

export function LanguageSelector({ value, onChange, disabled }: LanguageSelectorProps) {
  const selectId = useId()
  return (
    <div className="language-selector">
      <label htmlFor={selectId} className="language-selector__label">
        Език на отговора
      </label>
      <select
        id={selectId}
        className="language-selector__select"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value as AnswerLanguage)}
      >
        {OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  )
}
