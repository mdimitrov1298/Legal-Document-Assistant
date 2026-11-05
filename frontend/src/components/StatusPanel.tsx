import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { ApiError } from '@/api/client'
import type { HealthResponse, ModelsResponse } from '@/api/types'
import { getModels } from '@/api/system'

interface StatusPanelProps {
  health: HealthResponse | null
  error: ApiError | null
  loading: boolean
  onRefresh: () => void
}

export function StatusPanel({ health, error, loading, onRefresh }: StatusPanelProps) {
  const { t } = useTranslation()
  return (
    <section className="status-panel" aria-label={t('status.heading')} aria-live="polite">
      <div className="status-panel__header">
        <h2>{t('status.heading')}</h2>
        <button type="button" className="button--ghost" onClick={onRefresh}>
          {t('status.refresh')}
        </button>
      </div>
      {health ? (
        <HealthRows health={health} />
      ) : loading ? (
        <p className="muted">{t('status.apiChecking')}</p>
      ) : (
        <p className="warn">
          {t('status.apiUnavailable')}
          {error && <span className="muted"> ({error.message})</span>}
        </p>
      )}
    </section>
  )
}

function HealthRows({ health }: { health: HealthResponse }) {
  const { t } = useTranslation()
  const { ollama, embeddings, chunking } = health
  const [models, setModels] = useState<ModelsResponse | null>(null)

  useEffect(() => {
    getModels().then(setModels).catch(() => {})
  }, [health])

  const routing = models?.routing

  return (
    <dl className="status-grid">
      <dt>{t('status.api')}</dt>
      <dd>
        <span className={health.status === 'ok' ? 'ok' : 'warn'}>
          {health.status === 'ok' ? t('status.working') : t('status.limited')}
        </span>{' '}
        <span className="muted">v{health.version}</span>
      </dd>

      <dt>{t('status.ollama')}</dt>
      <dd>
        {ollama.reachable ? (
          <span className="ok">{t('status.reachable')}</span>
        ) : (
          <span className="warn">{t('status.unreachable')}</span>
        )}{' '}
        <span className="muted">{ollama.base_url}</span>
      </dd>

      <dt>{t('status.model')}</dt>
      <dd>
        <code>{ollama.model}</code>{' '}
        {ollama.model_present === true && <span className="ok">{t('status.downloaded')}</span>}
        {ollama.model_present === false && (
          <span className="warn">
            {t('status.notDownloaded')}: <code>ollama pull {ollama.model}</code>
          </span>
        )}
      </dd>

      {routing && (
        <>
          <dt>{t('status.routing')}</dt>
          <dd>
            {routing.mode === 'language' ? (
              <span className="ok">
                {t('status.byLanguage')} (BG: <code>{routing.model_bg}</code>, EN:{' '}
                <code>{routing.model_en}</code>)
              </span>
            ) : (
              <span className="muted">{t('status.disabled')}</span>
            )}
          </dd>
        </>
      )}

      <dt>{t('status.embeddings')}</dt>
      <dd>
        {embeddings.backend}
        {embeddings.backend !== embeddings.backend_configured && (
          <span className="warn"> ({t('status.configured')}: {embeddings.backend_configured})</span>
        )}
        , <code>{embeddings.model}</code>, {embeddings.device}
      </dd>

      <dt>{t('status.chunking')}</dt>
      <dd>
        {chunking.size} {t('status.characters')}, {t('status.overlap')} {chunking.overlap}
      </dd>
    </dl>
  )
}
