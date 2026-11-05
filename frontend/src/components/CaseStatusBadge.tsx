import { useTranslation } from 'react-i18next'
import type { CaseStatus } from '@/api/types'

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  const { t } = useTranslation()
  
  const label = t(`case.status.${status}`)
  const hint = t(`case.statusHint.${status}`)

  return (
    <span className={`status-badge status-badge--${status}`} title={hint}>
      {label}
    </span>
  )
}
