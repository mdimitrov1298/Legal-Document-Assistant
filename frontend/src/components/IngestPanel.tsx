import { useTranslation } from 'react-i18next'
import type { CaseResponse, IndexStatsResponse, IngestResponse } from '@/api/types'
import { formatDateTime, formatDuration } from '@/utils/format'

interface IngestPanelProps {
  caseData: CaseResponse
  indexStats: IndexStatsResponse | null
  result: IngestResponse | null
  busy: boolean
  /** Another action is running. */
  locked: boolean
  onIngest: () => Promise<void>
}

export function IngestPanel({
  caseData,
  indexStats,
  result,
  busy,
  locked,
  onIngest,
}: IngestPanelProps) {
  const { t } = useTranslation()
  const hasDocuments = caseData.document_count > 0
  const reingest = caseData.status === 'ingested' || caseData.status === 'stale'

  return (
    <section className="panel" aria-labelledby="ingest-heading">
      <h2 id="ingest-heading">{t('ingest.heading')}</h2>
      <p className="muted">{t('ingest.description')}</p>

      {caseData.status === 'stale' && (
        <p className="notice notice--warn" role="status">
          {t('ingest.staleWarning')}
        </p>
      )}

      <button type="button" disabled={busy || locked || !hasDocuments} onClick={() => void onIngest()}>
        {busy ? t('ingest.indexing') : reingest ? t('ingest.reindex') : t('ingest.index')}
      </button>
      {!hasDocuments && <p className="muted">{t('ingest.needDocument')}</p>}

      {indexStats && (
        <dl className="meta-grid" aria-label={t('ingest.statsTitle')}>
          <dt>{t('ingest.chunksInIndex')}</dt>
          <dd>{indexStats.chunk_count}</dd>
          <dt>{t('status.embeddings')}</dt>
          <dd>
            {indexStats.embedding_backend}, <code>{indexStats.embedding_model}</code>
          </dd>
          <dt>{t('ingest.collection')}</dt>
          <dd>
            <code>{indexStats.collection}</code>
          </dd>
          <dt>{t('ingest.indexedAt')}</dt>
          <dd>{formatDateTime(indexStats.ingested_at)}</dd>
        </dl>
      )}

      {result && (
        <p className="meta" role="status">
          {t('ingest.lastResult', {
            documents: t('ingest.document', { count: result.documents_processed }),
            chunks: t('ingest.chunk', { count: result.chunks_indexed }),
            chunkSize: result.chunk_size,
            overlap: result.chunk_overlap,
            duration: formatDuration(result.duration_ms),
          })}
        </p>
      )}
    </section>
  )
}
