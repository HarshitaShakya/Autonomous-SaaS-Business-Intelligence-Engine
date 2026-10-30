/**
 * React hooks that fetch live data from the backend API.
 * Each hook returns { data, loading, error } and falls back to mock values
 * when the backend is unreachable (VITE_USE_MOCK=true or network failure).
 *
 * Import these hooks in your page components instead of importing raw
 * values from '@/data/mock' to get real backend data.
 */

import { useEffect, useState } from 'react'
import { api, IS_MOCK_MODE } from './api'
import type {
  OverviewData,
  Segment,
  ChurnRiskData,
  CustomerPage,
  CustomerDetail,
  Feature,
  Recommendation,
  ActionsData,
  PipelineData,
  SettingsData,
  Anomaly,
} from './api'

// ---------------------------------------------------------------------------
// Generic hook factory
// ---------------------------------------------------------------------------

interface FetchState<T> {
  data: T | null
  loading: boolean
  error: string | null
}

function useFetch<T>(fetcher: () => Promise<T>, deps: unknown[] = []): FetchState<T> {
  const [state, setState] = useState<FetchState<T>>({ data: null, loading: true, error: null })

  useEffect(() => {
    if (IS_MOCK_MODE) {
      setState({ data: null, loading: false, error: 'mock mode' })
      return
    }

    let cancelled = false
    setState((s) => ({ ...s, loading: true, error: null }))

    fetcher()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null })
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : String(err)
          setState({ data: null, loading: false, error: msg })
        }
      })

    return () => {
      cancelled = true
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}

// ---------------------------------------------------------------------------
// Exported hooks
// ---------------------------------------------------------------------------

/** Live overview KPIs: MRR, at-risk counts, pending approvals, etc. */
export function useOverview() {
  return useFetch<OverviewData>(() => api.overview())
}

/** All user behaviour segments from the backend. */
export function useSegments() {
  return useFetch<Segment[]>(() => api.segments())
}

/** Churn risk summary: survival curve, churn reasons, expected cancellations. */
export function useChurnRisk() {
  return useFetch<ChurnRiskData>(() => api.churnRisk())
}

/** Paginated customer list with filtering, sorting, and search. */
export function useCustomers(params?: Parameters<typeof api.customers>[0]) {
  return useFetch<CustomerPage>(() => api.customers(params), [JSON.stringify(params)])
}

/** Single customer detail including survival curve & recommendations. */
export function useCustomerDetail(id: string) {
  return useFetch<CustomerDetail>(() => api.customer(id), [id])
}

/** Feature causal-impact analysis results. */
export function useFeatures() {
  return useFetch<Feature[]>(() => api.features())
}

/** All recommendations from the Strategy agent. */
export function useRecommendations() {
  return useFetch<Recommendation[]>(() => api.recommendations())
}

/** Action log + stats. */
export function useActions() {
  return useFetch<ActionsData>(() => api.actions())
}

/** Pipeline metadata: agent timings, classifier metrics, etc. */
export function usePipelineMetadata() {
  return useFetch<PipelineData>(() => api.pipelineMetadata())
}

/** Application settings: mode, thresholds, schedule. */
export function useSettings() {
  return useFetch<SettingsData>(() => api.settings())
}

/** Anomaly alerts from the last pipeline run. */
export function useAnomalies() {
  return useFetch<Anomaly[]>(() => api.anomalies())
}
