import { useCallback, useEffect, useState } from 'react'
import { getCase } from '@/api/cases'
import { isAbortError, toApiError, type ApiError } from '@/api/client'
import { deleteDocument, listDocuments, uploadDocument } from '@/api/documents'
import { askCase, getIndexStats, ingestCase, searchCase, summarizeCase, verifyClaim } from '@/api/rag'
import type {
  AnswerLanguage,
  AskResponse,
  CaseResponse,
  DocumentResponse,
  IndexStatsResponse,
  IngestResponse,
  SearchMode,
  SearchResponse,
  SummarizeResponse,
  VerifyResponse,
} from '@/api/types'

export type CaseAction = 'load' | 'upload' | 'deleteDocument' | 'ingest' | 'summarize' | 'verify' | 'search' | 'ask'

interface Snapshot {
  caseData: CaseResponse
  documents: DocumentResponse[]
  indexStats: IndexStatsResponse | null
}

export function canQuery(caseData: CaseResponse | null): boolean {
  return caseData?.status === 'ingested' || caseData?.status === 'stale'
}

async function fetchSnapshot(caseId: string, signal?: AbortSignal): Promise<Snapshot> {
  const [caseData, documents] = await Promise.all([
    getCase(caseId, signal),
    listDocuments(caseId, signal),
  ])
  let indexStats: IndexStatsResponse | null = null
  if (canQuery(caseData)) {
    try {
      indexStats = await getIndexStats(caseId, signal)
    } catch (err) {
      // Index stats are informational; a missing index must not block the view.
      if (isAbortError(err)) throw err
    }
  }
  return { caseData, documents, indexStats }
}

/**
 * State and actions for a single case. Mount with `key={caseId}` so that
 * switching cases starts from a clean state.
 */
export function useCaseDetail(caseId: string, onCaseChange?: (caseData: CaseResponse) => void) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [ingestResult, setIngestResult] = useState<IngestResponse | null>(null)
  const [summary, setSummary] = useState<SummarizeResponse | null>(null)
  const [verification, setVerification] = useState<VerifyResponse | null>(null)
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null)
  const [askResult, setAskResult] = useState<AskResponse | null>(null)
  const [busy, setBusy] = useState<CaseAction | null>('load')
  const [error, setError] = useState<ApiError | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    fetchSnapshot(caseId, controller.signal).then(
      (next) => {
        setSnapshot(next)
        setBusy(null)
        onCaseChange?.(next.caseData)
      },
      (err: unknown) => {
        if (isAbortError(err)) return
        setError(toApiError(err))
        setBusy(null)
      },
    )
    return () => controller.abort()
  }, [caseId, onCaseChange])

  const run = useCallback(async (action: CaseAction, fn: () => Promise<void>) => {
    setBusy(action)
    setError(null)
    try {
      await fn()
    } catch (err) {
      setError(toApiError(err))
    } finally {
      setBusy(null)
    }
  }, [])

  const refresh = useCallback(async () => {
    const next = await fetchSnapshot(caseId)
    setSnapshot(next)
    onCaseChange?.(next.caseData)
  }, [caseId, onCaseChange])

  const resetResults = useCallback(() => {
    setIngestResult(null)
    setSummary(null)
    setVerification(null)
    setSearchResult(null)
    setAskResult(null)
  }, [])

  const upload = useCallback(
    (files: File[]) =>
      run('upload', async () => {
        try {
          for (const file of files) await uploadDocument(caseId, file)
        } finally {
          resetResults()
          await refresh()
        }
      }),
    [caseId, run, refresh, resetResults],
  )

  const removeDocument = useCallback(
    (documentId: string) =>
      run('deleteDocument', async () => {
        await deleteDocument(caseId, documentId)
        resetResults()
        await refresh()
      }),
    [caseId, run, refresh, resetResults],
  )

  const ingest = useCallback(
    () =>
      run('ingest', async () => {
        const result = await ingestCase(caseId)
        resetResults()
        setIngestResult(result)
        await refresh()
      }),
    [caseId, run, refresh, resetResults],
  )

  const summarize = useCallback(
    (answerLanguage: AnswerLanguage = 'auto') =>
      run('summarize', async () => {
        const body = answerLanguage === 'auto' ? {} : { answer_language: answerLanguage }
        setSummary(await summarizeCase(caseId, body))
      }),
    [caseId, run],
  )

  const verify = useCallback(
    (claim: string, answerLanguage: AnswerLanguage = 'auto') =>
      run('verify', async () => {
        const body =
          answerLanguage === 'auto'
            ? { claim }
            : { claim, answer_language: answerLanguage }
        setVerification(await verifyClaim(caseId, body))
      }),
    [caseId, run],
  )

  const search = useCallback(
    (query: string, mode: SearchMode = 'hybrid') =>
      run('search', async () => {
        setSearchResult(await searchCase(caseId, { query, mode }))
      }),
    [caseId, run],
  )

  const ask = useCallback(
    (question: string, answerLanguage: AnswerLanguage = 'auto') =>
      run('ask', async () => {
        const body =
          answerLanguage === 'auto'
            ? { question }
            : { question, answer_language: answerLanguage }
        setAskResult(await askCase(caseId, body))
      }),
    [caseId, run],
  )

  const clearError = useCallback(() => setError(null), [])

  return {
    caseData: snapshot?.caseData ?? null,
    documents: snapshot?.documents ?? [],
    indexStats: snapshot?.indexStats ?? null,
    ingestResult,
    summary,
    verification,
    searchResult,
    askResult,
    busy,
    error,
    clearError,
    upload,
    removeDocument,
    ingest,
    summarize,
    verify,
    search,
    ask,
  }
}
