import type { ApiError } from '@/api/client'
import type { HealthResponse } from '@/api/types'

interface StatusPanelProps {
  health: HealthResponse | null
  error: ApiError | null
  loading: boolean
  onRefresh: () => void
}

export function StatusPanel({ health, error, loading, onRefresh }: StatusPanelProps) {
  return (
    <section className="status-panel" aria-label="Състояние на системата" aria-live="polite">
      <div className="status-panel__header">
        <h2>Състояние</h2>
        <button type="button" className="button--ghost" onClick={onRefresh}>
          Обнови
        </button>
      </div>
      {health ? (
        <HealthRows health={health} />
      ) : loading ? (
        <p className="muted">Проверка на API...</p>
      ) : (
        <p className="warn">
          API е недостъпен: стартирайте backend на порт 8000.
          {error && <span className="muted"> ({error.message})</span>}
        </p>
      )}
    </section>
  )
}

function HealthRows({ health }: { health: HealthResponse }) {
  const { ollama, embeddings, chunking } = health
  return (
    <dl className="status-grid">
      <dt>API</dt>
      <dd>
        <span className={health.status === 'ok' ? 'ok' : 'warn'}>
          {health.status === 'ok' ? 'работи' : 'ограничен режим'}
        </span>{' '}
        <span className="muted">v{health.version}</span>
      </dd>

      <dt>Ollama</dt>
      <dd>
        {ollama.reachable ? (
          <span className="ok">достъпен</span>
        ) : (
          <span className="warn">недостъпен: генерирането използва заглушки</span>
        )}{' '}
        <span className="muted">{ollama.base_url}</span>
      </dd>

      <dt>Модел</dt>
      <dd>
        <code>{ollama.model}</code>{' '}
        {ollama.model_present === true && <span className="ok">изтеглен</span>}
        {ollama.model_present === false && (
          <span className="warn">
            не е изтеглен: <code>ollama pull {ollama.model}</code>
          </span>
        )}
      </dd>

      <dt>Embeddings</dt>
      <dd>
        {embeddings.backend}
        {embeddings.backend !== embeddings.backend_configured && (
          <span className="warn"> (конфигуриран: {embeddings.backend_configured})</span>
        )}
        , <code>{embeddings.model}</code>, {embeddings.device}
      </dd>

      <dt>Разделяне</dt>
      <dd>
        {chunking.size} символа, застъпване {chunking.overlap}
      </dd>
    </dl>
  )
}
