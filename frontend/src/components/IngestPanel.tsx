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
  const hasDocuments = caseData.document_count > 0
  const reingest = caseData.status === 'ingested' || caseData.status === 'stale'

  return (
    <section className="panel" aria-labelledby="ingest-heading">
      <h2 id="ingest-heading">Индексиране</h2>
      <p className="muted">
        Текстът се извлича, разделя на фрагменти и се записва във векторната база (Chroma).
      </p>

      {caseData.status === 'stale' && (
        <p className="notice notice--warn" role="status">
          Документите са променени след последното индексиране. Индексирайте отново, за да бъдат
          включени в резюмето и проверката.
        </p>
      )}

      <button
        type="button"
        disabled={busy || locked || !hasDocuments}
        onClick={() => void onIngest()}
      >
        {busy ? 'Индексиране...' : reingest ? 'Индексирай отново' : 'Индексирай'}
      </button>
      {!hasDocuments && <p className="muted">Първо качете поне един документ.</p>}

      {indexStats && (
        <dl className="meta-grid" aria-label="Текущ индекс">
          <dt>Фрагменти в индекса</dt>
          <dd>{indexStats.chunk_count}</dd>
          <dt>Embeddings</dt>
          <dd>
            {indexStats.embedding_backend}, <code>{indexStats.embedding_model}</code>
          </dd>
          <dt>Колекция</dt>
          <dd>
            <code>{indexStats.collection}</code>
          </dd>
          <dt>Индексиран на</dt>
          <dd>{formatDateTime(indexStats.ingested_at)}</dd>
        </dl>
      )}

      {result && (
        <p className="meta" role="status">
          Последно индексиране: {result.documents_processed} документа, {result.chunks_indexed}{' '}
          фрагмента (размер {result.chunk_size}, застъпване {result.chunk_overlap}) за{' '}
          {formatDuration(result.duration_ms)}.
        </p>
      )}
    </section>
  )
}
