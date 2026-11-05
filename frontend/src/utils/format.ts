export function formatDateTime(iso: string | null): string {
  if (!iso) return '-'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  
  // Use the current browser language or fall back to 'bg-BG'
  const locale = navigator.language || 'bg-BG'
  const formatter = new Intl.DateTimeFormat(locale, {
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
