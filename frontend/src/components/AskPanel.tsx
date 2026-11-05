import { useId, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import type { AnswerLanguage, AskResponse } from '@/api/types'
import { CitationList } from '@/components/CitationList'
import { GenerationInfo } from '@/components/GenerationInfo'
import { LanguageSelector } from '@/components/LanguageSelector'
import { formatDuration } from '@/utils/format'

const QUESTION_MIN = 3
const QUESTION_MAX = 2000

interface AskPanelProps {
  result: AskResponse | null
  ready: boolean
  busy: boolean
  locked: boolean
  onAsk: (question: string, answerLanguage: AnswerLanguage) => Promise<void>
}

export function AskPanel({ result, ready, busy, locked, onAsk }: AskPanelProps) {
  const { t } = useTranslation()
  const [question, setQuestion] = useState('')
  const [answerLang, setAnswerLang] = useState<AnswerLanguage>('auto')
  const questionId = useId()
  const trimmed = question.trim()
  const valid = trimmed.length >= QUESTION_MIN && trimmed.length <= QUESTION_MAX

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (valid) void onAsk(trimmed, answerLang)
  }

  return (
    <section className="panel" aria-labelledby="ask-heading" aria-busy={busy}>
      <h2 id="ask-heading">{t('ask.heading')}</h2>
      <form onSubmit={handleSubmit}>
        <label htmlFor={questionId} className="visually-hidden">
          {t('ask.questionLabel')}
        </label>
        <textarea
          id={questionId}
          rows={3}
          value={question}
          maxLength={QUESTION_MAX}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t('ask.questionPlaceholder')}
          disabled={!ready}
        />
        <div className="panel__controls">
          <LanguageSelector value={answerLang} onChange={setAnswerLang} disabled={busy || locked} />
          <button type="submit" disabled={!ready || busy || locked || !valid}>
            {busy ? t('ask.searching') : t('ask.ask')}
          </button>
        </div>
      </form>
      {!ready && <p className="muted">{t('ask.needIndex')}</p>}
      {result && (
        <div className="result">
          <GenerationInfo
            model={result.model}
            stubbed={result.stubbed}
            durationMs={result.duration_ms}
          />
          <p className="muted">
            {t('ask.question')}: {result.question}
          </p>
          <p>
            {t('ask.status')}: <AnswerStatusBadge status={result.answer_status} />
          </p>
          <div className="result__text">
            <p>{result.answer}</p>
          </div>
          <div className="ask-timing">
            <span>
              {t('ask.retrieval')}: {formatDuration(result.retrieval_ms)}
            </span>
            <span>
              {t('ask.generation')}: {formatDuration(result.generation_ms)}
            </span>
          </div>
          <h3>
            {t('ask.citationsHeading')} ({result.citations.length})
          </h3>
          <CitationList items={result.citations} label={t('ask.citationsLabel')} />
          <details>
            <summary>
              {t('ask.allRetrievedHeading')} ({result.retrieved_quotes.length})
            </summary>
            <CitationList items={result.retrieved_quotes} label={t('ask.allRetrievedHeading')} />
          </details>
        </div>
      )}
    </section>
  )
}

function AnswerStatusBadge({ status }: { status: string }) {
  const { t } = useTranslation()
  const isAnswered = status === 'answered'
  return (
    <span
      className={`answer-status ${isAnswered ? 'answer-status--answered' : 'answer-status--not-found'}`}
    >
      {isAnswered ? t('ask.answered') : t('ask.notFound')}
    </span>
  )
}
