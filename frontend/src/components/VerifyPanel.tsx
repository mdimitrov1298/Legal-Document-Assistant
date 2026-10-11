import { useId, type FormEvent, useState } from 'react'
import type { AnswerLanguage, VerifyResponse } from '@/api/types'
import { CitationList } from '@/components/CitationList'
import { GenerationInfo } from '@/components/GenerationInfo'
import { LanguageSelector } from '@/components/LanguageSelector'
import { VerdictBadge } from '@/components/VerdictBadge'

const CLAIM_MIN = 3
const CLAIM_MAX = 1000

interface VerifyPanelProps {
  result: VerifyResponse | null
  /** The case has an index that can be queried. */
  ready: boolean
  busy: boolean
  /** Another action is running. */
  locked: boolean
  onVerify: (claim: string, answerLanguage: AnswerLanguage) => Promise<void>
  /** Externally controlled claim text (e.g. from SearchPanel "use as claim"). */
  claim: string
  /** Notify parent when claim text changes. */
  onClaimChange: (claim: string) => void
}

export function VerifyPanel({ result, ready, busy, locked, onVerify, claim, onClaimChange }: VerifyPanelProps) {
  const [answerLang, setAnswerLang] = useState<AnswerLanguage>('auto')
  const claimId = useId()
  const trimmed = claim.trim()
  const valid = trimmed.length >= CLAIM_MIN && trimmed.length <= CLAIM_MAX

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (valid) void onVerify(trimmed, answerLang)
  }

  return (
    <section className="panel" aria-labelledby="verify-heading" aria-busy={busy}>
      <h2 id="verify-heading">Проверка на твърдение</h2>
      <form onSubmit={handleSubmit}>
        <label htmlFor={claimId} className="visually-hidden">
          Твърдение за проверка
        </label>
        <textarea
          id={claimId}
          rows={3}
          value={claim}
          maxLength={CLAIM_MAX}
          onChange={(e) => onClaimChange(e.target.value)}
          placeholder="Въведете фактическо твърдение за проверка по документите..."
          disabled={!ready}
        />
        <div className="panel__controls">
          <LanguageSelector value={answerLang} onChange={setAnswerLang} disabled={busy || locked} />
          <button type="submit" disabled={!ready || busy || locked || !valid}>
            {busy ? 'Проверка...' : 'Провери'}
          </button>
        </div>
      </form>
      {!ready && <p className="muted">Първо индексирайте документите.</p>}
      {result && (
        <div className="result">
          <GenerationInfo
            model={result.model}
            stubbed={result.stubbed}
            durationMs={result.duration_ms}
          />
          <p className="muted">Твърдение: {result.claim}</p>
          <p>
            Резултат: <VerdictBadge verdict={result.verdict} />
          </p>
          <p>{result.rationale}</p>
          <h3>Подкрепящи цитати ({result.supporting_quotes.length})</h3>
          <CitationList items={result.supporting_quotes} label="Подкрепящи цитати" />
          <h3>Опровергаващи цитати ({result.denying_quotes.length})</h3>
          <CitationList items={result.denying_quotes} label="Опровергаващи цитати" />
          <details>
            <summary>Всички извлечени фрагменти ({result.retrieved_quotes.length})</summary>
            <CitationList items={result.retrieved_quotes} label="Всички извлечени фрагменти" />
          </details>
        </div>
      )}
    </section>
  )
}
