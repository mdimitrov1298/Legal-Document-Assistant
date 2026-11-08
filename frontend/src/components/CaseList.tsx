import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { CaseResponse } from '@/api/types'
import { CaseStatusBadge } from '@/components/CaseStatusBadge'
import { formatDateTime } from '@/utils/format'

interface CaseListProps {
  cases: CaseResponse[]
  selectedId: string | null
  loading: boolean
  /** Another list action is running. */
  locked: boolean
  onSelect: (caseId: string) => void
  onRename: (caseId: string, title: string) => Promise<boolean>
  onDelete: (caseId: string) => Promise<boolean>
}

export function CaseList({
  cases,
  selectedId,
  loading,
  locked,
  onSelect,
  onRename,
  onDelete,
}: CaseListProps) {
  const { t } = useTranslation()
  if (loading && !cases.length) return <p className="muted">{t('case.loading')}</p>
  if (!cases.length) return <p className="muted">{t('case.noCases')}</p>

  return (
    <ul className="case-list" aria-label={t('case.list')}>
      {cases.map((c) => (
        <CaseListItem
          key={c.id}
          caseData={c}
          selected={c.id === selectedId}
          locked={locked}
          onSelect={onSelect}
          onRename={onRename}
          onDelete={onDelete}
        />
      ))}
    </ul>
  )
}

interface CaseListItemProps {
  caseData: CaseResponse
  selected: boolean
  locked: boolean
  onSelect: (caseId: string) => void
  onRename: (caseId: string, title: string) => Promise<boolean>
  onDelete: (caseId: string) => Promise<boolean>
}

function CaseListItem({
  caseData,
  selected,
  locked,
  onSelect,
  onRename,
  onDelete,
}: CaseListItemProps) {
  const { t } = useTranslation()
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState(caseData.title)
  const trimmed = title.trim()

  function startEditing() {
    setTitle(caseData.title)
    setEditing(true)
  }

  async function handleRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!trimmed || trimmed === caseData.title) {
      setEditing(false)
      return
    }
    if (await onRename(caseData.id, trimmed)) setEditing(false)
  }

  function handleDelete() {
    const confirmed = window.confirm(t('case.confirmDelete', { title: caseData.title }))
    if (confirmed) void onDelete(caseData.id)
  }

  return (
    <li className={`case-list__item${selected ? ' case-list__item--selected' : ''}`}>
      {editing ? (
        <form className="case-list__rename" onSubmit={(e) => void handleRename(e)}>
          <input
            type="text"
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
            aria-label={t('case.newTitle')}
            autoFocus
          />
          <button type="submit" disabled={locked || !trimmed}>
            {t('case.save')}
          </button>
          <button type="button" className="button--ghost" onClick={() => setEditing(false)}>
            {t('case.cancel')}
          </button>
        </form>
      ) : (
        <>
          <button
            type="button"
            className="case-list__select"
            onClick={() => onSelect(caseData.id)}
            aria-current={selected ? 'true' : undefined}
          >
            <span className="case-list__title">{caseData.title}</span>
            <span className="case-list__meta">
              <CaseStatusBadge status={caseData.status} />
              <span className="muted">
                {caseData.document_count} {t('case.documents')}, {formatDateTime(caseData.created_at)}
              </span>
            </span>
          </button>
          <div className="case-list__actions">
            <button
              type="button"
              className="button--ghost"
              disabled={locked}
              onClick={startEditing}
              aria-label={t('case.renameAction', { title: caseData.title })}
            >
              {t('case.rename')}
            </button>
            <button
              type="button"
              className="button--danger"
              disabled={locked}
              onClick={handleDelete}
              aria-label={t('case.deleteAction', { title: caseData.title })}
            >
              {t('case.delete')}
            </button>
          </div>
        </>
      )}
    </li>
  )
}
