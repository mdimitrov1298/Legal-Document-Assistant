import { request } from '@/api/client'
import type { DocumentResponse } from '@/api/types'

const documentsPath = (caseId: string) => `/cases/${encodeURIComponent(caseId)}/documents`

export function listDocuments(caseId: string, signal?: AbortSignal): Promise<DocumentResponse[]> {
  return request<DocumentResponse[]>(documentsPath(caseId), { signal })
}

export function uploadDocument(caseId: string, file: File): Promise<DocumentResponse> {
  const form = new FormData()
  form.append('file', file)
  return request<DocumentResponse>(documentsPath(caseId), { method: 'POST', form })
}

export function deleteDocument(caseId: string, documentId: string): Promise<void> {
  return request<void>(`${documentsPath(caseId)}/${encodeURIComponent(documentId)}`, {
    method: 'DELETE',
  })
}
