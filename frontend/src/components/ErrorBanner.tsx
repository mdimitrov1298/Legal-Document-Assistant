import { useTranslation } from 'react-i18next'
import type { ApiError } from '@/api/client'

interface ErrorBannerProps {
  error: ApiError | null
  onDismiss?: () => void
}

export function ErrorBanner({ error, onDismiss }: ErrorBannerProps) {
  const { t } = useTranslation()
  if (!error) return null
  return (
    <div className="error-banner" role="alert">
      <div className="error-banner__body">
        <p className="error-banner__message">{error.message}</p>
        <p className="error-banner__meta">
          {t('error.code')}: <code>{error.code}</code>
          {error.status > 0 && <> (HTTP {error.status})</>}
          {error.requestId && (
            <>
              , {t('error.requestId')}: <code>{error.requestId}</code>
            </>
          )}
        </p>
        {error.details && (
          <details>
            <summary>{t('error.details')}</summary>
            <pre>{JSON.stringify(error.details, null, 2)}</pre>
          </details>
        )}
      </div>
      {onDismiss && (
        <button
          type="button"
          className="button--ghost"
          onClick={onDismiss}
          aria-label={t('error.dismissLabel')}
        >
          {t('error.dismiss')}
        </button>
      )}
    </div>
  )
}
