import { useId } from 'react'

const ACCEPT = '.pdf,.txt,text/plain,application/pdf'

interface DocumentUploadProps {
  busy: boolean
  /** Another action is running. */
  locked: boolean
  onUpload: (files: File[]) => Promise<void>
}

export function DocumentUpload({ busy, locked, onUpload }: DocumentUploadProps) {
  const inputId = useId()
  return (
    <div className="document-upload">
      <label htmlFor={inputId}>Добавете PDF или TXT файлове (на български)</label>
      <input
        id={inputId}
        type="file"
        accept={ACCEPT}
        multiple
        disabled={busy || locked}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? [])
          e.target.value = ''
          if (files.length) void onUpload(files)
        }}
      />
      {busy && <p className="muted">Качване...</p>}
    </div>
  )
}
