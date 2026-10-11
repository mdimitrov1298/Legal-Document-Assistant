import { useId, useState, type FormEvent } from 'react'
import type { SearchMode, SearchResponse, SearchResult } from '@/api/types'
import { formatDuration } from '@/utils/format'

const QUERY_MIN = 1
const QUERY_MAX = 1000

const MODE_OPTIONS: { value: SearchMode; label: string }[] = [
  { value: 'hybrid', label: 'Хибридно' },
  { value: 'semantic', label: 'Семантично' },
  { value: 'keyword', label: 'По ключови думи' },
]

interface SearchPanelProps {
  result: SearchResponse | null
  ready: boolean
  busy: boolean
  locked: boolean
  onSearch: (query: string, mode: SearchMode) => Promise<void>
  onUseAsClaim: (text: string) => void
}

export function SearchPanel({ result, ready, busy, locked, onSearch, onUseAsClaim }: SearchPanelProps) {
  const [query, setQuery] = useState('')
  const [mode, setMode] = useState<SearchMode>('hybrid')
  const queryId = useId()
  const modeId = useId()
  const trimmed = query.trim()
  const valid = trimmed.length >= QUERY_MIN && trimmed.length <= QUERY_MAX

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (valid) void onSearch(trimmed, mode)
  }

  return (
    <section className="panel" aria-labelledby="search-heading" aria-busy={busy}>
      <h2 id="search-heading">Търсене в документите</h2>
      <form onSubmit={handleSubmit}>
        <label htmlFor={queryId} className="visually-hidden">
          Заявка за търсене
        </label>
        <input
          id={queryId}
          type="text"
          value={query}
          maxLength={QUERY_MAX}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Въведете заявка за търсене..."
          disabled={!ready}
        />
        <div className="panel__controls">
          <div className="search-mode-selector">
            <label htmlFor={modeId} className="search-mode-selector__label">
              Режим:
            </label>
            <select
              id={modeId}
              value={mode}
              onChange={(e) => setMode(e.target.value as SearchMode)}
              disabled={busy || locked}
              className="search-mode-selector__select"
            >
              {MODE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <button type="submit" disabled={!ready || busy || locked || !valid}>
            {busy ? 'Търсене...' : 'Търси'}
          </button>
        </div>
      </form>
      {!ready && <p className="muted">Първо индексирайте документите.</p>}
      {result && (
        <div className="result">
          <p className="generation-info">
            <span>Режим: {result.mode}</span>
            <span>Резултати: {result.results.length}</span>
            <span>Време: {formatDuration(result.duration_ms)}</span>
          </p>
          {result.results.length === 0 && (
            <p className="muted">Няма намерени резултати.</p>
          )}
          <ol className="search-results" aria-label="Резултати от търсенето">
            {result.results.map((r, i) => (
              <SearchResultItem
                key={`${r.chunk_id}:${String(i)}`}
                item={r}
                query={result.query}
                onUseAsClaim={onUseAsClaim}
              />
            ))}
          </ol>
        </div>
      )}
    </section>
  )
}

interface SearchResultItemProps {
  item: SearchResult
  query: string
  onUseAsClaim: (text: string) => void
}

function SearchResultItem({ item, onUseAsClaim }: SearchResultItemProps) {
  return (
    <li className="search-result">
      <div className="search-result__meta">
        <span className="search-result__file">{item.document_filename}</span>
        <span>фрагмент #{item.chunk_index}</span>
        <span className="search-result__score" title="Резултат от търсенето">
          резултат {item.score.toFixed(3)}
        </span>
      </div>
      <div className="search-result__text">
        <HighlightedText text={item.text} highlights={item.highlights} />
      </div>
      <button
        type="button"
        className="search-result__use-btn"
        onClick={() => onUseAsClaim(item.text)}
        title="Използвай текста като твърдение за проверка"
      >
        Използвай като твърдение
      </button>
    </li>
  )
}

interface HighlightedTextProps {
  text: string
  highlights: { start: number; end: number }[]
}

function HighlightedText({ text, highlights }: HighlightedTextProps) {
  if (highlights.length === 0) return <>{text}</>

  const sorted = [...highlights].sort((a, b) => a.start - b.start)
  const parts: { text: string; highlighted: boolean }[] = []
  let cursor = 0

  for (const hl of sorted) {
    if (hl.start > cursor) {
      parts.push({ text: text.slice(cursor, hl.start), highlighted: false })
    }
    parts.push({ text: text.slice(hl.start, hl.end), highlighted: true })
    cursor = hl.end
  }
  if (cursor < text.length) {
    parts.push({ text: text.slice(cursor), highlighted: false })
  }

  return (
    <>
      {parts.map((part, i) =>
        part.highlighted ? (
          <mark key={String(i)}>{part.text}</mark>
        ) : (
          <span key={String(i)}>{part.text}</span>
        ),
      )}
    </>
  )
}
