import type { DocumentResponse } from '@/api/types'
import { LanguageBadge } from '@/components/LanguageBadge'
import { formatBytes, formatDateTime } from '@/utils/format'

interface DocumentListProps {
  documents: DocumentResponse[]
  /** Another action is running. */
  locked: boolean
  onDelete: (documentId: string) => Promise<void>
}

export function DocumentList({ documents, locked, onDelete }: DocumentListProps) {
  if (!documents.length) return <p className="muted">Няма качени документи.</p>

  function handleDelete(doc: DocumentResponse) {
    const confirmed = window.confirm(
      `Да се изтрие ли документът „${doc.filename}“? Индексът ще трябва да се обнови.`,
    )
    if (confirmed) void onDelete(doc.id)
  }

  return (
    <ul className="document-list">
      {documents.map((doc) => (
        <li key={doc.id} className="document-list__item">
          <div>
            <span className="document-list__name">
              {doc.filename} <LanguageBadge language={doc.language} />
            </span>
            <span className="muted">
              {formatBytes(doc.size_bytes)}, {formatDateTime(doc.uploaded_at)}
            </span>
          </div>
          <button
            type="button"
            className="button--danger"
            disabled={locked}
            onClick={() => handleDelete(doc)}
            aria-label={`Изтрий документа ${doc.filename}`}
          >
            Изтрий
          </button>
        </li>
      ))}
    </ul>
  )
}
