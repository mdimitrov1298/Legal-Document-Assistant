import type { CaseStatus } from '@/api/types'

const LABELS: Record<CaseStatus, string> = {
  empty: 'Без документи',
  uploaded: 'Неиндексиран',
  ingested: 'Индексиран',
  stale: 'Остарял индекс',
}

const HINTS: Record<CaseStatus, string> = {
  empty: 'Качете документи, за да започнете.',
  uploaded: 'Документите са качени, но още не са индексирани.',
  ingested: 'Индексът е актуален.',
  stale: 'Документите са променени след последното индексиране.',
}

export function CaseStatusBadge({ status }: { status: CaseStatus }) {
  return (
    <span className={`status-badge status-badge--${status}`} title={HINTS[status]}>
      {LABELS[status]}
    </span>
  )
}
