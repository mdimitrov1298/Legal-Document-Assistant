import { useCallback, useEffect, useState } from 'react'
import { isAbortError, toApiError, type ApiError } from '@/api/client'
import { getHealth } from '@/api/system'
import type { HealthResponse } from '@/api/types'

export const HEALTH_POLL_MS = 15_000

export interface HealthState {
  health: HealthResponse | null
  error: ApiError | null
  loading: boolean
  refresh: () => void
}

export function useHealth(intervalMs: number = HEALTH_POLL_MS): HealthState {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const poll = () => {
      getHealth(controller.signal).then(
        (next) => {
          setHealth(next)
          setError(null)
          setLoading(false)
        },
        (err: unknown) => {
          if (isAbortError(err)) return
          setHealth(null)
          setError(toApiError(err))
          setLoading(false)
        },
      )
    }
    poll()
    const timer = window.setInterval(poll, intervalMs)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [intervalMs, nonce])

  const refresh = useCallback(() => setNonce((n) => n + 1), [])

  return { health, error, loading, refresh }
}
