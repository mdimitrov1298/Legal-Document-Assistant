import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { AnswerLanguage, SummarizeResponse } from '@/api/types'
import { CitationList } from '@/components/CitationList'
import { GenerationInfo } from '@/components/GenerationInfo'
import { LanguageSelector } from '@/components/LanguageSelector'

interface SummaryPanelProps {
  result: SummarizeResponse | null
  /** The case has an index that can be queried. */
  ready: boolean
  busy: boolean
  /** Another action is running. */
  locked: boolean
  onSummarize: (answerLanguage: AnswerLanguage) => Promise<void>
}

export function SummaryPanel({ result, ready, busy, locked, onSummarize }: SummaryPanelProps) {
  const { t } = useTranslation()
  const [answerLang, setAnswerLang] = useState<AnswerLanguage>('auto')

  return (
    <section className="panel" aria-labelledby="summary-heading" aria-busy={busy}>
      <h2 id="summary-heading">{t('summary.heading')}</h2>
      <div className="panel__controls">
        <LanguageSelector value={answerLang} onChange={setAnswerLang} disabled={busy || locked} />
        <button
          type="button"
          disabled={!ready || busy || locked}
          onClick={() => void onSummarize(answerLang)}
        >
          {busy ? t('summary.summarizing') : t('summary.summarize')}
        </button>
      </div>
      {!ready && <p className="muted">{t('summary.needIndex')}</p>}
      {result && (
        <div className="result">
          <GenerationInfo
            model={result.model}
            stubbed={result.stubbed}
            durationMs={result.duration_ms}
            chunksUsed={result.chunks_used}
          />
          <pre className="result__text">{result.summary}</pre>
          <h3>
            {t('summary.citationsHeading')} ({result.citations.length})
          </h3>
          <CitationList items={result.citations} label={t('summary.citationsHeading')} />
        </div>
      )}
    </section>
  )
}
