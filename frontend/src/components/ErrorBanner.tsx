import type { ApiError } from '@/api/client'

interface ErrorBannerProps {
  error: ApiError | null
  onDismiss?: () => void
}

export function ErrorBanner({ error, onDismiss }: ErrorBannerProps) {
  if (!error) return null
  return (
    <div className="error-banner" role="alert">
      <div className="error-banner__body">
        <p className="error-banner__message">{error.message}</p>
        <p className="error-banner__meta">
          Код: <code>{error.code}</code>
          {error.status > 0 && <> (HTTP {error.status})</>}
          {error.requestId && (
            <>
              , ID на заявката: <code>{error.requestId}</code>
            </>
          )}
        </p>
        {error.details && (
          <details>
            <summary>Подробности</summary>
            <pre>{JSON.stringify(error.details, null, 2)}</pre>
          </details>
        )}
      </div>
      {onDismiss && (
        <button
          type="button"
          className="button--ghost"
          onClick={onDismiss}
          aria-label="Затвори съобщението за грешка"
        >
          Затвори
        </button>
      )}
    </div>
  )
}
