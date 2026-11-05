import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { CaseCreate } from '@/api/types'
import { CaseForm } from '@/components/CaseForm'
import { CaseList } from '@/components/CaseList'
import { CaseWorkspace } from '@/components/CaseWorkspace'
import { Disclaimer } from '@/components/Disclaimer'
import { ErrorBanner } from '@/components/ErrorBanner'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import { StatusPanel } from '@/components/StatusPanel'
import { useCases } from '@/hooks/useCases'
import { useHealth } from '@/hooks/useHealth'

export default function App() {
  const { t } = useTranslation()
  const health = useHealth()
  const cases = useCases()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  async function handleCreate(body: CaseCreate): Promise<boolean> {
    const created = await cases.create(body)
    if (created) setSelectedId(created.id)
    return created !== null
  }

  async function handleDelete(caseId: string): Promise<boolean> {
    const ok = await cases.remove(caseId)
    if (ok && caseId === selectedId) setSelectedId(null)
    return ok
  }

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__title-bar">
          <div>
            <h1>{t('app.title')}</h1>
            <p className="tagline">{t('app.tagline')}</p>
          </div>
          <LanguageSwitcher />
        </div>
        <StatusPanel
          health={health.health}
          error={health.error}
          loading={health.loading}
          onRefresh={health.refresh}
        />
      </header>

      <div className="app__body">
        <aside className="sidebar" aria-label={t('case.list')}>
          <section className="panel" aria-labelledby="new-case-heading">
            <h2 id="new-case-heading">{t('case.new')}</h2>
            <CaseForm busy={cases.busy === 'create'} onCreate={handleCreate} />
          </section>
          <section className="panel" aria-labelledby="case-list-heading">
            <div className="panel__header">
              <h2 id="case-list-heading">
                {t('case.list')} ({cases.cases.length})
              </h2>
              <button
                type="button"
                className="button--ghost"
                onClick={cases.reload}
                disabled={cases.busy !== null}
              >
                {t('status.refresh')}
              </button>
            </div>
            <ErrorBanner error={cases.error} onDismiss={cases.clearError} />
            <CaseList
              cases={cases.cases}
              selectedId={selectedId}
              loading={cases.busy === 'load'}
              locked={cases.busy !== null}
              onSelect={setSelectedId}
              onRename={cases.rename}
              onDelete={handleDelete}
            />
          </section>
        </aside>

        <main className="main">
          {selectedId ? (
            <CaseWorkspace key={selectedId} caseId={selectedId} onCaseChange={cases.upsert} />
          ) : (
            <p className="placeholder">{t('app.placeholder')}</p>
          )}
        </main>
      </div>

      <Disclaimer />
    </div>
  )
}
