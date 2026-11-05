import { useTranslation } from 'react-i18next'
import type { Verdict } from '@/api/types'

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const { t } = useTranslation()
  const label = t(`verify.verdict.${verdict}`)

  return (
    <span className={`verdict verdict--${verdict}`} aria-label={t('verify.verdictLabel', { verdict: label })}>
      {label}
    </span>
  )
}
