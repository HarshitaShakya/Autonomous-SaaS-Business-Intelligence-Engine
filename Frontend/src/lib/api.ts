/**
 * Typed API client for the BI Engine backend.
 *
 * All data fetching goes through this module. When VITE_USE_MOCK=true
 * (or when the backend is unreachable), falls back to mock data so
 * the UI still runs.
 */

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'

// ---------------------------------------------------------------------------
// Types (shaped by what the UI needs)
// ---------------------------------------------------------------------------

export type RiskLevel = 'High' | 'Medium' | 'Low'
export type Confidence = 'High' | 'Medium' | 'Low'
export type LogStatus = 'Executed' | 'Failed' | 'Dry-run' | 'Queued' | 'Running'

export interface OverviewData {
  accounts: number
  mrr: number
  at_risk: number
  mrr_at_risk: number
  mrr_at_risk_share: number
  churn_90: number
  pending_approvals: number
  actions_executed_30d: number
  last_run: string | null
  mode: string
  risk_distribution: { level: RiskLevel; accounts: number; range: string }[]
  kpi_trends: null // Sample-labeled until run history exists
  _sample_labeled: string[]
}

export interface Segment {
  id: string
  cluster_id: number
  name: string
  color: string
  accounts: number
  avg_mrr: number
  avg_risk: number
  risk_level: RiskLevel
  at_risk: number
  mrr_at_risk: number
  risk_trend: number
  risk_series: number[] | null
  flags: string[]
  summary: string
  position: { depth: number; frequency: number }
  profile: { metric: string; delta: number }[]
  engagement: number[] | null
  centroid_features: Record<string, number>
  is_anomalous: boolean
  mean_survival_6m: number
  mean_hazard_rate: number
  churn_reason_distribution: Record<string, number>
  _sample_labeled: string[]
}

export interface ChurnRiskData {
  accounts: number
  at_risk: number
  mrr_at_risk: number
  mrr_at_risk_share: number
  total_mrr: number
  expected_cancellations: { window: string; accounts: number }[]
  churn_reasons: { reason: string; share: number; detail: string }[]
  survival: Record<string, number>[]
  survival_segments: string[]
}

export interface Customer {
  customer_id: string
  name: string
  segment_id: number | null
  segment_label: string
  plan: string | null
  tenure_months: number
  mrr: number
  risk_score: number
  risk_level: RiskLevel
  days: number | null
  days_lo: number | null
  days_hi: number | null
  reason: string
  survival_6m: number
  hazard_rate: number
  drivers: string[]
}

export interface CustomerPage {
  customers: Customer[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface CustomerDetail extends Customer {
  survival_curve: { day: number; account: number }[] | null
  recommendations: {
    recommendation_id: string
    action_type: string
    justification: string
    status: string
  }[]
  timeline: null
  _sample_labeled: string[]
}

export interface Feature {
  id: string
  name: string
  feature_name: string
  lift: number
  lo: number
  hi: number
  naive: number
  significant: boolean
  p_value: number | null
  sample_size: number
  adoption: string | null
  responding: string[]
  explanation: string
  _sample_labeled: string[]
}

export interface Recommendation {
  recommendation_id: string
  id: string
  title: string
  verb: string
  action_type: string
  action_parameters: Record<string, unknown>
  segment_label: string
  segment_id: number | null
  justification: string
  confidence_score: number
  confidence: Confidence
  estimated_impact: number
  mrr_retained: number
  urgency: string
  segment_risk: Record<string, unknown>
  causal_evidence: Record<string, unknown>
  evidence: { label: string; value: string }[]
  lift: number
  lo: number
  hi: number
  status: string
  decided_at: string | null
  decided_by: string | null
  reject_reason: string | null
  mode: string
}

export interface ActionLogRow {
  id: string
  time: string
  recommendation: string
  rec_id?: string
  type: string
  segment_id: number | null
  segment_label: string
  approved_by: string
  status: LogStatus
  accounts: number
  result?: string
  error?: string
  payload: Record<string, unknown>
  decided_at?: string
}

export interface ActionsData {
  log: ActionLogRow[]
  stats: { label: string; value: string; hint: string }[]
  mode: string
  experiment: null
  outcome: null
  _sample_labeled: string[]
}

export interface PipelineStage {
  id: string
  name: string
  short: string
  duration: string
  status: string
}

export interface PipelineData {
  pipeline_metadata: Record<string, unknown>
  agents: PipelineStage[]
  loaded_at: string | null
  total_duration: string
  feature_analysis_method: string
  behavior_method: string
  classifier_metrics: Record<string, number>
  survival_concordance: number
  adapter: string
  n_records: number
}

export interface RunRecord {
  run_id: string
  started_at: string
  completed_at: string | null
  duration_seconds: number | null
  status: string
  note: string
  n_records: number
}

export interface SettingsData {
  mode: string
  thresholds: { high: number; medium: number; window_days: number }
  schedule: string
  require_approval: boolean
  approvers: null
  integrations: null
  _sample_labeled: string[]
}

export interface Anomaly {
  id: string
  tone: 'bad' | 'warn' | 'good' | 'failed'
  title: string
  detail: string
  when: string
  segment_id?: number
  retry_action_id?: string
}

export interface StatusResponse {
  status: string
  loaded_at: string | null
  pipeline_metadata: Record<string, unknown>
  mode: string
}

// ---------------------------------------------------------------------------
// Fetch helper
// ---------------------------------------------------------------------------

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? body.message ?? detail
    } catch { /* ignore */ }
    throw new ApiError(res.status, detail)
  }

  return res.json()
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export const api = {
  // Health
  status: () => apiFetch<StatusResponse>('/api/status'),

  // Overview
  overview: () => apiFetch<OverviewData>('/api/overview'),

  // Segments
  segments: () => apiFetch<Segment[]>('/api/segments'),

  // Churn Risk
  churnRisk: () => apiFetch<ChurnRiskData>('/api/churn-risk'),

  // Customers (paginated)
  customers: (params?: {
    page?: number
    page_size?: number
    sort_by?: string
    sort_dir?: 'asc' | 'desc'
    segment?: string
    reason?: string
    risk_level?: string
    search?: string
    min_risk?: number
  }) => {
    const qs = new URLSearchParams()
    if (params) {
      for (const [k, v] of Object.entries(params)) {
        if (v !== undefined && v !== null) qs.set(k, String(v))
      }
    }
    return apiFetch<CustomerPage>(`/api/customers?${qs}`)
  },

  // Customer detail
  customer: (id: string) => apiFetch<CustomerDetail>(`/api/customers/${encodeURIComponent(id)}`),

  // Features
  features: () => apiFetch<Feature[]>('/api/features'),

  // Recommendations
  recommendations: () => apiFetch<Recommendation[]>('/api/recommendations'),

  // Approve/Reject
  decide: (body: {
    recommendation_id: string
    decision: 'approved' | 'rejected'
    reason?: string
    idempotency_key?: string
  }) => apiFetch<{
    recommendation_id: string
    decision: string
    action_agent_result: Record<string, unknown> | null
    decided_at: string
    audit_id: string | null
    approver: string
  }>('/api/recommendations/decide', {
    method: 'POST',
    body: JSON.stringify(body),
  }),

  // Actions
  actions: () => apiFetch<ActionsData>('/api/actions'),

  // Retry action
  retryAction: (actionId: string) => apiFetch<{ status: string }>(`/api/actions/${encodeURIComponent(actionId)}/retry`, { method: 'POST' }),

  // Pipeline metadata
  pipelineMetadata: () => apiFetch<PipelineData>('/api/pipeline-metadata'),

  // Runs
  runs: () => apiFetch<RunRecord[]>('/api/runs'),

  // Refresh
  refresh: () => apiFetch<{ status: string; loaded_at: string; n_records: number; run_id: string | null }>('/api/refresh', { method: 'POST' }),

  // Settings
  settings: () => apiFetch<SettingsData>('/api/settings'),

  // Set mode
  setMode: (mode: string, confirmation?: string) =>
    apiFetch<{ mode: string; changed_at: string }>('/api/settings/mode', {
      method: 'POST',
      body: JSON.stringify({ mode, confirmation }),
    }),

  // Set thresholds
  setThresholds: (thresholds: Record<string, number>) =>
    apiFetch<{ thresholds: Record<string, number> }>('/api/settings/thresholds', {
      method: 'POST',
      body: JSON.stringify(thresholds),
    }),

  // Set schedule
  setSchedule: (schedule: string) =>
    apiFetch<{ schedule: string }>('/api/settings/schedule', {
      method: 'POST',
      body: JSON.stringify({ schedule }),
    }),

  // Anomalies
  anomalies: () => apiFetch<Anomaly[]>('/api/anomalies'),
}

// ---------------------------------------------------------------------------
// Export mock-mode flag for components that need to show "Sample data" labels
// ---------------------------------------------------------------------------
export const IS_MOCK_MODE = USE_MOCK
export { ApiError }
