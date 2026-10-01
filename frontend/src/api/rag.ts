import { request } from '@/api/client'
import type {
  IndexStatsResponse,
  IngestResponse,
  SummarizeRequest,
  SummarizeResponse,
  VerifyRequest,
  VerifyResponse,
} from '@/api/types'

const casePath = (caseId: string) => `/cases/${encodeURIComponent(caseId)}`

export function ingestCase(caseId: string): Promise<IngestResponse> {
  return request<IngestResponse>(`${casePath(caseId)}/ingest`, { method: 'POST' })
}

export function getIndexStats(caseId: string, signal?: AbortSignal): Promise<IndexStatsResponse> {
  return request<IndexStatsResponse>(`${casePath(caseId)}/index`, { signal })
}

export function summarizeCase(
  caseId: string,
  body: SummarizeRequest = {},
): Promise<SummarizeResponse> {
  return request<SummarizeResponse>(`${casePath(caseId)}/summarize`, {
    method: 'POST',
    json: body,
  })
}

export function verifyClaim(caseId: string, body: VerifyRequest): Promise<VerifyResponse> {
  return request<VerifyResponse>(`${casePath(caseId)}/verify`, { method: 'POST', json: body })
}
