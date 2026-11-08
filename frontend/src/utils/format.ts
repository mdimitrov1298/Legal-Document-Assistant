import i18n from '@/i18n/config'

function resolveDateLocale(): string {
  const lang = (i18n.language || 'bg').toLowerCase()
  return lang.startsWith('en') ? 'en-GB' : 'bg-BG'
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return '-'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso

  const formatter = new Intl.DateTimeFormat(resolveDateLocale(), {
    dateStyle: 'short',
    timeStyle: 'short',
  })
  return formatter.format(date)
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${String(bytes)} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDuration(ms: number): string {
  return ms < 1000 ? `${String(Math.round(ms))} ms` : `${(ms / 1000).toFixed(1)} s`
}
