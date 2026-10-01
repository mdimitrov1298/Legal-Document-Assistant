import { useCallback, useEffect, useState } from 'react'
import { createCase, deleteCase, listCases, updateCase } from '@/api/cases'
import { isAbortError, toApiError, type ApiError } from '@/api/client'
import type { CaseCreate, CaseResponse } from '@/api/types'

export type CasesAction = 'load' | 'create' | 'rename' | 'delete'

function sortNewestFirst(cases: CaseResponse[]): CaseResponse[] {
  return [...cases].sort((a, b) => b.created_at.localeCompare(a.created_at))
}

export function useCases() {
  const [cases, setCases] = useState<CaseResponse[]>([])
  const [busy, setBusy] = useState<CasesAction | null>('load')
  const [error, setError] = useState<ApiError | null>(null)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    listCases({}, controller.signal).then(
      (next) => {
        setCases(next)
        setBusy(null)
      },
      (err: unknown) => {
        if (isAbortError(err)) return
        setError(toApiError(err))
        setBusy(null)
      },
    )
    return () => controller.abort()
  }, [nonce])

  const reload = useCallback(() => {
    setBusy('load')
    setError(null)
    setNonce((n) => n + 1)
  }, [])

  const run = useCallback(
    async <T>(action: CasesAction, fn: () => Promise<T>): Promise<T | null> => {
      setBusy(action)
      setError(null)
      try {
        return await fn()
      } catch (err) {
        setError(toApiError(err))
        return null
      } finally {
        setBusy(null)
      }
    },
    [],
  )

  /** Inserts or replaces a case, e.g. after the detail view refreshed it. */
  const upsert = useCallback((next: CaseResponse) => {
    setCases((prev) =>
      prev.some((c) => c.id === next.id)
        ? prev.map((c) => (c.id === next.id ? next : c))
        : sortNewestFirst([next, ...prev]),
    )
  }, [])

  const create = useCallback(
    (body: CaseCreate) =>
      run('create', async () => {
        const created = await createCase(body)
        upsert(created)
        return created
      }),
    [run, upsert],
  )

  const rename = useCallback(
    async (caseId: string, title: string) => {
      const updated = await run('rename', () => updateCase(caseId, { title }))
      if (updated) upsert(updated)
      return updated !== null
    },
    [run, upsert],
  )

  const remove = useCallback(
    async (caseId: string) => {
      const ok = await run('delete', async () => {
        await deleteCase(caseId)
        return true
      })
      if (ok) setCases((prev) => prev.filter((c) => c.id !== caseId))
      return ok === true
    },
    [run],
  )

  const clearError = useCallback(() => setError(null), [])

  return { cases, busy, error, clearError, reload, upsert, create, rename, remove }
}
