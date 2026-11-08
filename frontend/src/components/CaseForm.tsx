import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { CaseCreate } from '@/api/types'

const TITLE_MAX = 200
const DESCRIPTION_MAX = 2000

interface CaseFormProps {
  busy: boolean
  onCreate: (body: CaseCreate) => Promise<boolean>
}

export function CaseForm({ busy, onCreate }: CaseFormProps) {
  const { t } = useTranslation()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const trimmed = title.trim()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!trimmed) return
    const created = await onCreate({
      title: trimmed,
      description: description.trim() || undefined,
    })
    if (created) {
      setTitle('')
      setDescription('')
    }
  }

  return (
    <form className="case-form" onSubmit={(e) => void handleSubmit(e)}>
      <label className="field">
        <span>{t('case.titleLabel')}</span>
        <input
          type="text"
          value={title}
          maxLength={TITLE_MAX}
          required
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t('case.titlePlaceholder')}
        />
      </label>
      <label className="field">
        <span>{t('case.descriptionLabel')}</span>
        <textarea
          rows={2}
          value={description}
          maxLength={DESCRIPTION_MAX}
          onChange={(e) => setDescription(e.target.value)}
        />
      </label>
      <button type="submit" disabled={busy || !trimmed}>
        {busy ? t('case.creating') : t('case.create')}
      </button>
    </form>
  )
}
