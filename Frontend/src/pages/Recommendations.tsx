import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { CheckCircle2, Inbox, PartyPopper, RotateCw, XCircle } from 'lucide-react'
import { recommendations, segments, type ActionType, type Confidence, type ActionLogRow } from '@/data/mock'
import { fmtInt, fmtMoney } from '@/lib/format'
import { useApp } from '@/state/AppState'
import RecommendationCard from '@/components/RecommendationCard'
import { ActionTypeTag, Button, Card, EmptyState, PageHeader, SegmentChip, Select, Skeleton, StatusPill, Tabs } from '@/components/ui'

type Tab = 'pending' | 'approved' | 'rejected' | 'executed'
const tabIds: Tab[] = ['pending', 'approved', 'rejected', 'executed']

function ExecutedCard({ row }: { row: ActionLogRow }) {
  const { retry } = useApp()
  return (
    <Card as="article" aria-label={row.recommendation} className="p-5">
      <div className="flex flex-wrap items-center gap-2">
        <SegmentChip id={row.segment} />
        <ActionTypeTag type={row.type} />
        <StatusPill status={row.status} />
        <span className="ml-auto text-xs text-fg-2">
          {row.time} · approved by {row.approvedBy}
        </span>
      </div>
      <h3 className="mt-3 text-base font-semibold text-fg">{row.recommendation}</h3>
      {row.status === 'Failed' ? (
        <div className="mt-3 flex items-center gap-3 rounded-md border border-risk-high/35 bg-risk-high/8 px-3 py-2 text-sm text-fg">
          <XCircle size={16} className="shrink-0 text-risk-high" aria-hidden />
          <span className="flex-1">
            {row.error}. <span className="text-fg-2">{fmtInt(row.accounts)} accounts were not reached.</span>
          </span>
          <Button size="sm" variant="secondary" icon={<RotateCw size={14} aria-hidden />} onClick={() => retry(row.id)}>
            Retry
          </Button>
        </div>
      ) : (
        <p className="mt-2 flex items-center gap-2 text-sm text-fg-2">
          {row.status === 'Executed' && <CheckCircle2 size={14} className="text-risk-low" aria-hidden />}
          <span className="num">
            {fmtInt(row.accounts)} accounts · {row.result}
          </span>
        </p>
      )}
    </Card>
  )
}

export default function Recommendations() {
  const { state, pendingIds, setSegment } = useApp()
  const [params, setParams] = useSearchParams()
  const tab = (tabIds.includes(params.get('tab') as Tab) ? params.get('tab') : 'pending') as Tab
  const expand = params.get('expand')
  const [type, setType] = useState<'all' | ActionType>('all')
  const [conf, setConf] = useState<'all' | Confidence>('all')
  const loading = state.lastRun.loading

  const byStatus = useMemo(
    () => ({
      pending: recommendations.filter((r) => pendingIds.includes(r.id)).sort((a, b) => b.mrrRetained - a.mrrRetained),
      approved: recommendations.filter((r) => state.recs[r.id]?.status === 'approved'),
      rejected: recommendations.filter((r) => state.recs[r.id]?.status === 'rejected'),
    }),
    [pendingIds, state.recs],
  )
  const executed = state.log.filter((l) => l.status === 'Executed' || l.status === 'Failed' || l.status === 'Running')

  const matches = (seg: string | number | null, t: ActionType | string, c?: Confidence) =>
    (state.segmentFilter === 'all' || (seg !== null && String(seg) === state.segmentFilter)) && (type === 'all' || t === type) && (conf === 'all' || !c || c === conf)

  const list = tab === 'executed' ? [] : byStatus[tab].filter((r) => matches(r.segment, r.type, r.confidence))
  const execList = executed.filter((l) => matches(l.segment, l.type))
  const filtered = type !== 'all' || conf !== 'all' || state.segmentFilter !== 'all'
  const totalPendingMrr = byStatus.pending.reduce((s, r) => s + r.mrrRetained, 0)

  useEffect(() => {
    if (!expand) return
    const t = window.setTimeout(() => {
      const el = document.getElementById(`rec-${expand}`)
      el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      el?.focus({ preventScroll: true })
    }, 60)
    return () => window.clearTimeout(t)
  }, [expand, tab])

  const setTab = (id: string) => setParams({ tab: id })

  const clear = () => {
    setType('all')
    setConf('all')
    setSegment('all')
  }

  return (
    <>
      <PageHeader
        title="Recommendations & Approvals"
        description="Retention actions proposed by the Strategy agent. Nothing is sent until you approve it."
        agent="Strategy agent (LLM)"
        agentStatus={`Completed ${state.lastRun.label}`}
      />

      <div className="col-span-12 flex items-center gap-6 rounded-card border border-decision/40 bg-decision/[0.06] px-5 py-3">
        <p className="text-sm text-fg">
          <span className="num font-semibold text-decision">{pendingIds.length}</span> waiting for your decision
          {pendingIds.length > 0 && (
            <span className="text-fg-2">
              {' '}
              · <span className="num font-medium text-fg">{fmtMoney(totalPendingMrr)}</span> est. MRR retained if all are approved
            </span>
          )}
        </p>
        <span className="ml-auto text-xs text-fg-2">
          Mode: <span className="font-semibold text-fg">{state.mode === 'live' ? 'Live' : 'Dry-run'}</span> · Approvals logged as Priya S.
        </span>
      </div>

      <div className="col-span-12">
        <Tabs
          label="Recommendation status"
          value={tab}
          onChange={setTab}
          tabs={[
            { id: 'pending', label: 'Pending', count: pendingIds.length, countTone: 'decision' },
            { id: 'approved', label: 'Approved', count: byStatus.approved.length },
            { id: 'rejected', label: 'Rejected', count: byStatus.rejected.length },
            { id: 'executed', label: 'Executed', count: executed.length },
          ]}
        />
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Select
            label="Segment"
            value={state.segmentFilter}
            onChange={(v) => setSegment(v as typeof state.segmentFilter)}
            options={[{ value: 'all', label: 'All segments' }, ...segments.map((s) => ({ value: s.id, label: s.name }))]}
          />
          <Select
            label="Action type"
            value={type}
            onChange={(v) => setType(v as typeof type)}
            options={[
              { value: 'all', label: 'All action types' },
              ...(['UI guide', 'Targeted email', 'A/B test', 'Pricing change'] as const).map((t) => ({ value: t, label: t })),
            ]}
          />
          {tab !== 'executed' && (
            <Select
              label="Confidence"
              value={conf}
              onChange={(v) => setConf(v as typeof conf)}
              options={[
                { value: 'all', label: 'Any confidence' },
                { value: 'High', label: 'High confidence' },
                { value: 'Medium', label: 'Medium confidence' },
                { value: 'Low', label: 'Low confidence' },
              ]}
            />
          )}
          {filtered && (
            <Button size="sm" variant="ghost" onClick={clear}>
              Clear filters
            </Button>
          )}
        </div>
      </div>

      <div id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} className="col-span-12 space-y-4">
        {loading ? (
          [0, 1, 2].map((i) => <Skeleton key={i} className="h-[260px] rounded-card" />)
        ) : tab === 'executed' ? (
          execList.length ? (
            execList.map((row) => <ExecutedCard key={row.id} row={row} />)
          ) : (
            <Card>
              <EmptyState icon={<Inbox size={18} aria-hidden />} title="Nothing executed matches these filters" action={filtered ? <Button size="sm" variant="secondary" onClick={clear}>Clear filters</Button> : undefined} />
            </Card>
          )
        ) : list.length ? (
          list.map((r) => (
            <div key={r.id} id={`rec-${r.id}`} tabIndex={-1} className="scroll-mt-6 rounded-card outline-none focus-visible:ring-2 focus-visible:ring-accent">
              <RecommendationCard rec={r} expanded={expand === r.id} />
            </div>
          ))
        ) : (
          <Card>
            {filtered && byStatus[tab].length ? (
              <EmptyState icon={<Inbox size={18} aria-hidden />} title="No recommendations match these filters" action={<Button size="sm" variant="secondary" onClick={clear}>Clear filters</Button>} />
            ) : tab === 'pending' ? (
              <EmptyState
                icon={<PartyPopper size={18} aria-hidden />}
                title="No pending recommendations — you're all caught up"
                body="The Strategy agent proposes new actions after each analysis run. The next run is at 06:00."
                action={
                  <Link to="/actions" className="text-xs font-semibold text-accent hover:underline">
                    See what's running
                  </Link>
                }
              />
            ) : tab === 'approved' ? (
              <EmptyState icon={<CheckCircle2 size={18} aria-hidden />} title="Nothing approved yet" body="Approved recommendations appear here while they wait to be executed." />
            ) : (
              <EmptyState icon={<XCircle size={18} aria-hidden />} title="Nothing rejected" body="Rejected recommendations and your reasons are kept here." />
            )}
          </Card>
        )}
      </div>
    </>
  )
}
