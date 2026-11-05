import { useTranslation } from 'react-i18next'
import type { Citation } from '@/api/types'

interface CitationListProps {
  items: Citation[]
  /** Accessible name for the list, e.g. "Цитати от резюмето". */
  label: string
  emptyLabel?: string
}

export function CitationList({ items, label, emptyLabel }: CitationListProps) {
  const { t } = useTranslation()
  const defaultEmptyLabel = emptyLabel ?? t('citation.noCitations')
  
  if (!items.length) return <p className="muted">{defaultEmptyLabel}</p>

  const nonVerbatim = items.filter((c) => !c.verbatim).length

  return (
    <>
      {nonVerbatim > 0 && (
        <p className="notice notice--warn" role="note">
          {t('citation.nonVerbatimWarning', { count: nonVerbatim, total: items.length })}
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
  const { t } = useTranslation()
  const source = `${c.document_filename}, ${t('citation.chunk')} ${String(c.chunk_index)}`
  
  return (
    <li className={`citation${c.verbatim ? '' : ' citation--non-verbatim'}`}>
      <div className="citation__meta">
        <span className="citation__file">{c.document_filename}</span>
        <span>
          {t('citation.chunk')} #{c.chunk_index}
        </span>
        {c.relevance !== null && (
          <span title={t('citation.relevanceTitle')}>
            {t('citation.relevance')} {c.relevance.toFixed(2)}
          </span>
        )}
        {!c.verbatim && (
          <span className="citation__flag" title={t('citation.nonVerbatimTitle')}>
            {t('citation.nonVerbatimFlag')}
          </span>
        )}
      </div>
      <blockquote
        aria-label={
          c.verbatim
            ? t('citation.verbatimLabel', { source })
            : t('citation.nonVerbatimLabel', { source })
        }
      >
        {c.quote}
      </blockquote>
    </li>
  )
}
