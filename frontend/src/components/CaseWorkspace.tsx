import type { CaseResponse } from '@/api/types'
import { CaseStatusBadge } from '@/components/CaseStatusBadge'
import { DocumentList } from '@/components/DocumentList'
import { DocumentUpload } from '@/components/DocumentUpload'
import { ErrorBanner } from '@/components/ErrorBanner'
import { IngestPanel } from '@/components/IngestPanel'
import { SummaryPanel } from '@/components/SummaryPanel'
import { VerifyPanel } from '@/components/VerifyPanel'
import { canQuery, useCaseDetail } from '@/hooks/useCaseDetail'

interface CaseWorkspaceProps {
  caseId: string
  onCaseChange: (caseData: CaseResponse) => void
}

export function CaseWorkspace({ caseId, onCaseChange }: CaseWorkspaceProps) {
  const detail = useCaseDetail(caseId, onCaseChange)
  const { caseData, documents, busy } = detail

  if (!caseData) {
    return (
      <div className="workspace">
        <ErrorBanner error={detail.error} onDismiss={detail.clearError} />
        {busy === 'load' && <p className="muted">Зареждане на казуса...</p>}
      </div>
    )
  }

  const queryable = canQuery(caseData)
  const locked = busy !== null

  return (
    <div className="workspace">
      <header className="workspace__header">
        <h2>{caseData.title}</h2>
        <CaseStatusBadge status={caseData.status} />
        {caseData.description && <p className="muted">{caseData.description}</p>}
      </header>

      <ErrorBanner error={detail.error} onDismiss={detail.clearError} />

      <section className="panel" aria-labelledby="documents-heading">
        <h2 id="documents-heading">Документи ({documents.length})</h2>
        <DocumentUpload busy={busy === 'upload'} locked={locked} onUpload={detail.upload} />
        <DocumentList documents={documents} locked={locked} onDelete={detail.removeDocument} />
      </section>

      <IngestPanel
        caseData={caseData}
        indexStats={detail.indexStats}
        result={detail.ingestResult}
        busy={busy === 'ingest'}
        locked={locked}
        onIngest={detail.ingest}
      />
      <SummaryPanel
        result={detail.summary}
        ready={queryable}
        busy={busy === 'summarize'}
        locked={locked}
        onSummarize={detail.summarize}
      />
      <VerifyPanel
        result={detail.verification}
        ready={queryable}
        busy={busy === 'verify'}
        locked={locked}
        onVerify={detail.verify}
      />
    </div>
  )
}
