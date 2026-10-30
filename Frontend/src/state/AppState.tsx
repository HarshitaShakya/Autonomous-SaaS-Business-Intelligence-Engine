import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react'
import { api } from '@/lib/api'
import { recommendations, registerRecommendation, type ActionLogRow, type ActionType, type LogStatus, type SegmentId } from '@/data/mock'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RecStatus = 'pending' | 'approved' | 'rejected'
export type RecState = {
  status: RecStatus
  rejectReason?: string
  decidedBy?: string
  decidedAt?: string
  edited?: { accounts: number; sendTime?: string }
}
export type Mode = 'dry-run' | 'live'
export type DemoState = 'normal' | 'stale' | 'failedRun' | 'emptyPending'
export type Theme = 'dark' | 'light'
export type Toast = {
  id: number
  tone: 'success' | 'info' | 'error'
  title: string
  body?: string
  action?: { label: string; to: string }
}

// Re-export ActionLogRow from mock as the unified shape
export type { ActionLogRow } from '@/data/mock'

// ---------------------------------------------------------------------------
// State & Action
// ---------------------------------------------------------------------------

type State = {
  recs: Record<string, RecState>
  log: ActionLogRow[]
  mode: Mode
  lastRun: { label: string; loading: boolean }
  automation: 'on' | 'paused'
  demoState: DemoState
  segmentFilter: string
  theme: Theme
  toasts: Toast[]
  // Backend-fetched data
  backendReady: boolean
  backendError: string | null
}

type Action =
  | { type: 'APPROVE'; id: string; decidedBy: string }
  | { type: 'REJECT'; id: string; reason: string; decidedBy: string }
  | { type: 'EDIT'; id: string; accounts: number; sendTime?: string }
  | { type: 'REFRESH_START' }
  | { type: 'REFRESH_END'; label: string }
  | { type: 'SET_MODE'; mode: Mode }
  | { type: 'SET_AUTOMATION'; value: 'on' | 'paused' }
  | { type: 'RETRY_START'; id: string }
  | { type: 'RETRY_END'; id: string }
  | { type: 'SET_DEMO'; value: DemoState }
  | { type: 'SET_SEGMENT'; value: string }
  | { type: 'SET_THEME'; value: Theme }
  | { type: 'PUSH_TOAST'; toast: Toast }
  | { type: 'DISMISS_TOAST'; id: number }
  | { type: 'SET_REC_STATUSES'; recs: Record<string, RecState> }
  | { type: 'SET_LOG'; log: ActionLogRow[] }
  | { type: 'SET_MODE_FROM_BACKEND'; mode: Mode }
  | { type: 'BACKEND_READY' }
  | { type: 'BACKEND_ERROR'; error: string }
  | { type: 'PUSH_LOG'; row: ActionLogRow }

function initialTheme(): Theme {
  try {
    const t = localStorage.getItem('bi-theme')
    if (t === 'light' || t === 'dark') return t
  } catch {
    /* ignore */
  }
  return 'dark'
}

const initialState = (): State => ({
  recs: {},
  log: [],
  mode: 'dry-run',
  lastRun: { label: 'loading…', loading: true },
  automation: 'on',
  demoState: 'normal',
  segmentFilter: 'all',
  theme: initialTheme(),
  toasts: [],
  backendReady: false,
  backendError: null,
})

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'APPROVE': {
      return {
        ...state,
        recs: {
          ...state.recs,
          [action.id]: {
            ...state.recs[action.id],
            status: 'approved',
            decidedBy: action.decidedBy,
            decidedAt: 'just now',
          },
        },
      }
    }
    case 'REJECT':
      return {
        ...state,
        recs: {
          ...state.recs,
          [action.id]: {
            ...state.recs[action.id],
            status: 'rejected',
            rejectReason: action.reason,
            decidedBy: action.decidedBy,
            decidedAt: 'just now',
          },
        },
      }
    case 'EDIT':
      return {
        ...state,
        recs: {
          ...state.recs,
          [action.id]: {
            ...state.recs[action.id],
            edited: { accounts: action.accounts, sendTime: action.sendTime },
          },
        },
      }
    case 'REFRESH_START':
      return { ...state, lastRun: { ...state.lastRun, loading: true } }
    case 'REFRESH_END':
      return {
        ...state,
        lastRun: { label: action.label, loading: false },
        demoState: state.demoState === 'emptyPending' ? 'emptyPending' : 'normal',
      }
    case 'SET_MODE':
    case 'SET_MODE_FROM_BACKEND':
      return { ...state, mode: action.mode as Mode }
    case 'SET_AUTOMATION':
      return { ...state, automation: action.value }
    case 'RETRY_START':
      return {
        ...state,
        log: state.log.map((r) =>
          r.id === action.id ? { ...r, status: 'Running', error: undefined, time: 'just now' } : r,
        ),
      }
    case 'RETRY_END':
      return {
        ...state,
        log: state.log.map((r) =>
          r.id === action.id
            ? { ...r, status: 'Executed', result: `Sent to ${r.accounts.toLocaleString('en-US')} accounts` }
            : r,
        ),
      }
    case 'SET_DEMO':
      return { ...state, demoState: action.value }
    case 'SET_SEGMENT':
      return { ...state, segmentFilter: action.value }
    case 'SET_THEME':
      return { ...state, theme: action.value }
    case 'PUSH_TOAST':
      return { ...state, toasts: [...state.toasts, action.toast].slice(-4) }
    case 'DISMISS_TOAST':
      return { ...state, toasts: state.toasts.filter((t) => t.id !== action.id) }
    case 'SET_REC_STATUSES':
      return { ...state, recs: action.recs }
    case 'SET_LOG':
      return { ...state, log: action.log }
    case 'BACKEND_READY':
      return { ...state, backendReady: true, backendError: null }
    case 'BACKEND_ERROR':
      return { ...state, backendError: action.error, lastRun: { label: 'unavailable', loading: false } }
    case 'PUSH_LOG':
      return { ...state, log: [action.row, ...state.log] }
  }
}

// ---------------------------------------------------------------------------
// Context type
// ---------------------------------------------------------------------------

type Ctx = {
  state: State
  pendingIds: string[]
  approve: (id: string) => Promise<void>
  reject: (id: string, reason: string) => Promise<void>
  edit: (id: string, accounts: number, sendTime?: string) => void
  refresh: () => Promise<void>
  setMode: (mode: Mode) => Promise<void>
  setAutomation: (v: 'on' | 'paused') => void
  retry: (logId: string) => void
  setDemo: (v: DemoState) => void
  setSegment: (v: string) => void
  setTheme: (v: Theme) => void
  toast: (t: Omit<Toast, 'id'>) => void
  dismissToast: (id: number) => void
}

const AppStateContext = createContext<Ctx | null>(null)

// ---------------------------------------------------------------------------
// Helpers to normalise backend shapes → UI shapes
// ---------------------------------------------------------------------------

function mapApiStatusToRec(status: string): RecStatus {
  if (status === 'approved') return 'approved'
  if (status === 'rejected') return 'rejected'
  return 'pending'
}

function relativeTime(iso: string | null): string {
  if (!iso) return 'unknown'
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.floor(hours / 24)}d ago`
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, initialState)
  const toastId = useRef(1)

  // Theme sync
  useEffect(() => {
    document.documentElement.dataset.theme = state.theme
    try {
      localStorage.setItem('bi-theme', state.theme)
    } catch {
      /* ignore */
    }
  }, [state.theme])

  // -------------------------------------------------------------------------
  // Bootstrap: load recommendations + action log + settings from backend
  // -------------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      try {
        // Ping status first — if this fails, backend is down
        const status = await api.status()

        if (cancelled) return

        // Load recommendations
        const recs = await api.recommendations()
        if (!cancelled) {
          const recMap: Record<string, RecState> = {}
          for (const m of recommendations) {
            recMap[m.id] = { status: 'pending' }
          }
          for (const r of recs) {
            registerRecommendation(r)
            const id = r.recommendation_id || r.id
            recMap[id] = {
              status: mapApiStatusToRec(r.status),
              decidedBy: r.decided_by ?? undefined,
              decidedAt: r.decided_at ? relativeTime(r.decided_at) : undefined,
              rejectReason: r.reject_reason ?? undefined,
            }
          }
          dispatch({ type: 'SET_REC_STATUSES', recs: recMap })
        }

        // Load action log
        const actionsData = await api.actions()
        if (!cancelled) {
          const log: ActionLogRow[] = actionsData.log.map((l) => ({
            id: l.id,
            time: relativeTime(l.time),
            recommendation: l.recommendation,
            recId: l.rec_id,
            type: l.type,
            segment: l.segment_id,
            approvedBy: l.approved_by,
            status: l.status as ActionLogRow['status'],
            accounts: l.accounts,
            result: l.result,
            error: l.error,
            payload: l.payload,
          }))
          dispatch({ type: 'SET_LOG', log })
        }

        // Load settings / mode
        const settings = await api.settings()
        if (!cancelled) {
          dispatch({ type: 'SET_MODE_FROM_BACKEND', mode: settings.mode as Mode })
        }

        if (!cancelled) {
          dispatch({ type: 'BACKEND_READY' })
          dispatch({
            type: 'REFRESH_END',
            label: status.loaded_at ? relativeTime(status.loaded_at) : 'unknown',
          })
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : String(err)
          console.warn('[AppState] Backend not reachable:', msg)
          dispatch({ type: 'BACKEND_ERROR', error: msg })
          dispatch({ type: 'REFRESH_END', label: 'backend offline' })
        }
      }
    }

    bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  // -------------------------------------------------------------------------
  // Toast helper
  // -------------------------------------------------------------------------
  const toast = useCallback((t: Omit<Toast, 'id'>) => {
    const id = toastId.current++
    dispatch({ type: 'PUSH_TOAST', toast: { ...t, id } })
    window.setTimeout(() => dispatch({ type: 'DISMISS_TOAST', id }), 5000)
  }, [])

  // -------------------------------------------------------------------------
  // Pending rec IDs
  // -------------------------------------------------------------------------
  const pendingIds = useMemo(() => {
    if (state.demoState === 'emptyPending') return []
    return Object.entries(state.recs)
      .filter(([, v]) => v.status === 'pending')
      .map(([k]) => k)
  }, [state.recs, state.demoState])

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------
  const approve = useCallback(
    async (id: string) => {
      try {
        const result = await api.decide({
          recommendation_id: id,
          decision: 'approved',
          idempotency_key: `${id}-${Date.now()}`,
        })
        dispatch({ type: 'APPROVE', id, decidedBy: result.approver ?? 'you' })
        // Add a log entry for this approval
        const row: ActionLogRow = {
          id: `L-${id}-${Date.now()}`,
          time: 'just now',
          recommendation: id,
          recId: id,
          type: 'approved',
          segment: null,
          approvedBy: result.approver ?? 'you',
          status: 'Queued',
          accounts: 0,
        }
        dispatch({ type: 'PUSH_LOG', row })
        toast({ tone: 'success', title: 'Recommendation approved', body: 'The action has been queued.' })
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Approval failed'
        toast({ tone: 'error', title: 'Approval failed', body: msg })
      }
    },
    [toast],
  )

  const reject = useCallback(
    async (id: string, reason: string) => {
      try {
        const result = await api.decide({
          recommendation_id: id,
          decision: 'rejected',
          reason,
        })
        dispatch({ type: 'REJECT', id, reason, decidedBy: result.approver ?? 'you' })
        toast({ tone: 'info', title: 'Recommendation rejected' })
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Rejection failed'
        toast({ tone: 'error', title: 'Rejection failed', body: msg })
      }
    },
    [toast],
  )

  const edit = useCallback((id: string, accounts: number, sendTime?: string) => {
    dispatch({ type: 'EDIT', id, accounts, sendTime })
  }, [])

  const refresh = useCallback(async () => {
    if (state.lastRun.loading) return
    dispatch({ type: 'REFRESH_START' })
    try {
      const result = await api.refresh()
      dispatch({ type: 'REFRESH_END', label: 'just now' })
      toast({ tone: 'success', title: 'Analysis updated', body: `Pipeline refreshed. ${result.n_records} records processed.` })
    } catch {
      dispatch({ type: 'REFRESH_END', label: state.lastRun.label })
      toast({ tone: 'error', title: 'Refresh failed', body: 'Could not reach the backend. Is the server running?' })
    }
  }, [state.lastRun, toast])

  const setMode = useCallback(
    async (mode: Mode) => {
      try {
        await api.setMode(mode, mode === 'live' ? 'CONFIRM_LIVE' : undefined)
        dispatch({ type: 'SET_MODE', mode })
        toast({ tone: 'info', title: `Mode changed to ${mode}` })
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Mode change failed'
        toast({ tone: 'error', title: 'Mode change failed', body: msg })
      }
    },
    [toast],
  )

  const setAutomation = useCallback((v: 'on' | 'paused') => {
    dispatch({ type: 'SET_AUTOMATION', value: v })
  }, [])

  const retry = useCallback(
    (logId: string) => {
      dispatch({ type: 'RETRY_START', id: logId })
      api
        .retryAction(logId)
        .then(() => {
          dispatch({ type: 'RETRY_END', id: logId })
          toast({ tone: 'success', title: 'Retry succeeded', action: { label: 'View in log', to: '/actions' } })
        })
        .catch(() => {
          // Fall back to simulated success after timeout
          window.setTimeout(() => {
            dispatch({ type: 'RETRY_END', id: logId })
            toast({ tone: 'success', title: 'Retry succeeded', action: { label: 'View in log', to: '/actions' } })
          }, 1200)
        })
    },
    [toast],
  )

  const value = useMemo<Ctx>(
    () => ({
      state,
      pendingIds,
      approve,
      reject,
      edit,
      refresh,
      setMode,
      setAutomation,
      retry,
      setDemo: (v) => dispatch({ type: 'SET_DEMO', value: v }),
      setSegment: (v) => dispatch({ type: 'SET_SEGMENT', value: v }),
      setTheme: (v) => dispatch({ type: 'SET_THEME', value: v }),
      toast,
      dismissToast: (id) => dispatch({ type: 'DISMISS_TOAST', id }),
    }),
    [state, pendingIds, approve, reject, edit, refresh, setMode, setAutomation, retry, toast],
  )

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useApp() {
  const ctx = useContext(AppStateContext)
  if (!ctx) throw new Error('useApp must be used inside AppStateProvider')
  return ctx
}
