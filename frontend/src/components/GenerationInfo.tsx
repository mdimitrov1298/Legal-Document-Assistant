import { useTranslation } from 'react-i18next'
import { formatDuration } from '@/utils/format'

interface GenerationInfoProps {
  model: string
  stubbed: boolean
  durationMs: number
  /** Number of retrieved chunks passed to the model, when known. */
  chunksUsed?: number
}

export function GenerationInfo({ model, stubbed, durationMs, chunksUsed }: GenerationInfoProps) {
  const { t } = useTranslation()
  return (
    <>
      {stubbed && (
        <p className="notice notice--warn" role="status">
          {t('generation.stubWarning')}
        </p>
      )}
      <p className="generation-info">
        <span className="model-tag" title={t('generation.modelTitle')}>
          {model}
        </span>
        {stubbed && <span className="model-tag model-tag--stub">{t('generation.stub')}</span>}
        <span>
          {t('generation.time')}: {formatDuration(durationMs)}
        </span>
        {chunksUsed !== undefined && (
          <span>
            {t('generation.chunksUsed')}: {chunksUsed}
          </span>
        )}
      </p>
    </>
  )
}
