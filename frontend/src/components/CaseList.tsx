import { useState, type FormEvent } from 'react'
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
  if (loading && !cases.length) return <p className="muted">Зареждане на казусите...</p>
  if (!cases.length) return <p className="muted">Все още няма казуси.</p>

  return (
    <ul className="case-list" aria-label="Казуси">
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
    const confirmed = window.confirm(
      `Да се изтрие ли казусът „${caseData.title}“ заедно с документите и индекса му?`,
    )
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
            aria-label="Ново заглавие на казуса"
            autoFocus
          />
          <button type="submit" disabled={locked || !trimmed}>
            Запази
          </button>
          <button type="button" className="button--ghost" onClick={() => setEditing(false)}>
            Отказ
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
                {caseData.document_count} док., {formatDateTime(caseData.created_at)}
              </span>
            </span>
          </button>
          <div className="case-list__actions">
            <button
              type="button"
              className="button--ghost"
              disabled={locked}
              onClick={startEditing}
              aria-label={`Преименувай казуса ${caseData.title}`}
            >
              Преименувай
            </button>
            <button
              type="button"
              className="button--danger"
              disabled={locked}
              onClick={handleDelete}
              aria-label={`Изтрий казуса ${caseData.title}`}
            >
              Изтрий
            </button>
          </div>
        </>
      )}
    </li>
  )
}
