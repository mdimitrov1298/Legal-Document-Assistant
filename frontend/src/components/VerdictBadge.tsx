import type { Verdict } from '@/api/types'

const LABELS: Record<Verdict, string> = {
  supported: 'Подкрепено',
  denied: 'Опровергано',
  inconclusive: 'Неустановено',
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return (
    <span className={`verdict verdict--${verdict}`} aria-label={`Резултат: ${LABELS[verdict]}`}>
      {LABELS[verdict]}
    </span>
  )
}
