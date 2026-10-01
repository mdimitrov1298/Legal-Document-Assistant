import type { Citation } from '@/api/types'

interface CitationListProps {
  items: Citation[]
  /** Accessible name for the list, e.g. "Цитати от резюмето". */
  label: string
  emptyLabel?: string
}

export function CitationList({ items, label, emptyLabel = 'Няма цитати.' }: CitationListProps) {
  if (!items.length) return <p className="muted">{emptyLabel}</p>

  const nonVerbatim = items.filter((c) => !c.verbatim).length

  return (
    <>
      {nonVerbatim > 0 && (
        <p className="notice notice--warn" role="note">
          {nonVerbatim} от {items.length} цитата не са открити дословно в документите. Сверете ги с
          оригиналния текст.
        </p>
      )}
      <ol className="citations" aria-label={label}>
        {items.map((c, i) => (
          <CitationItem key={`${c.chunk_id}:${String(i)}`} citation={c} />
        ))}
      </ol>
    </>
  )
}

function CitationItem({ citation: c }: { citation: Citation }) {
  const source = `${c.document_filename}, фрагмент ${String(c.chunk_index)}`
  return (
    <li className={`citation${c.verbatim ? '' : ' citation--non-verbatim'}`}>
      <div className="citation__meta">
        <span className="citation__file">{c.document_filename}</span>
        <span>фрагмент #{c.chunk_index}</span>
        {c.relevance !== null && (
          <span title="Сходство между заявката и фрагмента (по-високо е по-релевантно)">
            релевантност {c.relevance.toFixed(2)}
          </span>
        )}
        {!c.verbatim && (
          <span
            className="citation__flag"
            title="Текстът не съвпада точно с фрагмента от документа и може да е перифразиран от модела."
          >
            Цитатът не е дословен
          </span>
        )}
      </div>
      <blockquote aria-label={c.verbatim ? `Цитат от ${source}` : `Недословен цитат от ${source}`}>
        {c.quote}
      </blockquote>
    </li>
  )
}
