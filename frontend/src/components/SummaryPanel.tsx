import type { SummarizeResponse } from '@/api/types'
import { CitationList } from '@/components/CitationList'
import { GenerationInfo } from '@/components/GenerationInfo'

interface SummaryPanelProps {
  result: SummarizeResponse | null
  /** The case has an index that can be queried. */
  ready: boolean
  busy: boolean
  /** Another action is running. */
  locked: boolean
  onSummarize: () => Promise<void>
}

export function SummaryPanel({ result, ready, busy, locked, onSummarize }: SummaryPanelProps) {
  return (
    <section className="panel" aria-labelledby="summary-heading" aria-busy={busy}>
      <h2 id="summary-heading">Резюме с цитати</h2>
      <button type="button" disabled={!ready || busy || locked} onClick={() => void onSummarize()}>
        {busy ? 'Обобщаване...' : 'Обобщи'}
      </button>
      {!ready && <p className="muted">Първо индексирайте документите.</p>}
      {result && (
        <div className="result">
          <GenerationInfo
            model={result.model}
            stubbed={result.stubbed}
            durationMs={result.duration_ms}
            chunksUsed={result.chunks_used}
          />
          <pre className="result__text">{result.summary}</pre>
          <h3>Цитати ({result.citations.length})</h3>
          <CitationList items={result.citations} label="Цитати от резюмето" />
        </div>
      )}
    </section>
  )
}
