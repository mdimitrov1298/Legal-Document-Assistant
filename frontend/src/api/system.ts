import { request } from '@/api/client'
import type { HealthResponse, ModelsResponse } from '@/api/types'

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return request<HealthResponse>('/health', { signal })
}

export function getModels(signal?: AbortSignal): Promise<ModelsResponse> {
  return request<ModelsResponse>('/models', { signal })
}
