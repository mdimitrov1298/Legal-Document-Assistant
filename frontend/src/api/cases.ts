import { request } from '@/api/client'
import type { CaseCreate, CaseResponse, CaseUpdate, Pagination } from '@/api/types'

const casePath = (caseId: string) => `/cases/${encodeURIComponent(caseId)}`

export function listCases(page: Pagination = {}, signal?: AbortSignal): Promise<CaseResponse[]> {
  return request<CaseResponse[]>('/cases', {
    query: { skip: page.skip, limit: page.limit },
    signal,
  })
}

export function getCase(caseId: string, signal?: AbortSignal): Promise<CaseResponse> {
  return request<CaseResponse>(casePath(caseId), { signal })
}

export function createCase(body: CaseCreate): Promise<CaseResponse> {
  return request<CaseResponse>('/cases', { method: 'POST', json: body })
}

export function updateCase(caseId: string, body: CaseUpdate): Promise<CaseResponse> {
  return request<CaseResponse>(casePath(caseId), { method: 'PATCH', json: body })
}

export function deleteCase(caseId: string): Promise<void> {
  return request<void>(casePath(caseId), { method: 'DELETE' })
}
