import { useNavigate, Link } from 'react-router'
import { ArrowRight, Bot, CheckCircle2, ChevronRight, Cpu, Database, Flame, PartyPopper, ShieldAlert, Sparkles, TrendingDown, TrendingUp, TriangleAlert, XCircle, Zap } from 'lucide-react'
import { anomalies, headline, kpiTrends, recommendationById, riskDistribution, segments, type ActionLogRow } from '@/data/mock'
import { fmtInt, fmtMoney } from '@/lib/format'
import { useApp } from '@/state/AppState'
import KpiCard from '@/components/KpiCard'
import RecommendationCard from '@/components/RecommendationCard'
import DataTable from '@/components/DataTable'
import { RiskDistribution, SegmentHealthBars } from '@/components/charts'
import { ActionTypeTag, Button, Card, CardHeader, EmptyState, PageHeader, SegmentChip, Skeleton, StatusPill, cx } from '@/components/ui'

export default function Overview() {
  const { state, pendingIds, retry } = useApp()
  const navigate = useNavigate()
  const loading = state.lastRun.loading
  const top = pendingIds
    .map((id) => recommendationById[id])
    .filter((r): r is NonNullable<typeof r> => Boolean(r))
    .sort((a, b) => b.mrrRetained - a.mrrRetained)
    .slice(0, 3)

  return (
    <div className="col-span-12 space-y-6 anim-fade-in">
      <PageHeader
        title="Good morning, Priya"
        description="Autonomous churn prevention engine continuously monitoring 12,480 accounts and predicting revenue risk."
        agent="5 AI Agents"
        agentStatus={state.lastRun.loading ? 'Running ML Pipeline…' : `Synced ${state.lastRun.label}`}
      />

      {/* Executive AI Intelligence Briefing Banner */}
      <div className="relative overflow-hidden rounded-2xl border border-accent/25 bg-gradient-to-r from-accent/15 via-indigo-900/20 to-surface p-6 shadow-xl backdrop-blur-xl transition-all duration-300 hover:border-accent/40">
        <div className="absolute top-0 right-0 -mt-10 -mr-10 size-48 rounded-full bg-accent/10 blur-3xl" aria-hidden />
        <div className="absolute bottom-0 left-1/3 -mb-8 size-36 rounded-full bg-indigo-500/10 blur-2xl" aria-hidden />

        <div className="relative flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs font-semibold text-accent shadow-xs">
              <Sparkles size={13} className="text-accent animate-pulse" />
              <span>Autonomous Intelligence Briefing</span>
              <span className="size-1.5 rounded-full bg-accent pulse-radar" />
            </div>
            <h2 className="text-xl font-bold tracking-tight text-fg">
              {pendingIds.length > 0
                ? `${pendingIds.length} high-impact retention actions are ready for execution`
                : 'All retention recommendations processed and up to date'}
            </h2>
            <p className="max-w-2xl text-xs md:text-sm text-fg-2 leading-relaxed">
              Causal analysis detected building churn risk in <strong className="text-fg font-semibold">SMB</strong> and <strong className="text-fg font-semibold">Starters</strong> tiers. Executing top recommendations is estimated to protect up to <strong className="text-amber-400 font-semibold">$24,800/mo</strong> in recurring revenue.
            </p>
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-3">
            {pendingIds.length > 0 && (
              <Button
                variant="decision"
                size="md"
                onClick={() => navigate('/recommendations?tab=pending')}
                icon={<Zap size={15} />}
                className="shadow-lg shadow-amber-500/20 font-semibold"
              >
                Review {pendingIds.length} Actions
              </Button>
            )}
            <Button
              variant="secondary"
              size="md"
              onClick={() => navigate('/churn-risk')}
              icon={<ShieldAlert size={15} className="text-risk-high" />}
            >
              Analyze Churn Risk
            </Button>
          </div>
        </div>
      </div>

      {/* 5-Agent Live Telemetry Strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { name: '1. User Behavior', model: 'HDBSCAN + RFM', status: '5 Segments', icon: Cpu, color: 'text-indigo-400' },
          { name: '2. Churn Predictor', model: 'XGBoost (AUC 0.89)', status: '1,184 At Risk', icon: ShieldAlert, color: 'text-rose-400' },
          { name: '3. Causal Impact', model: 'DoWhy Double-ML', status: '6 Drivers', icon: Flame, color: 'text-amber-400' },
          { name: '4. Strategy Agent', model: 'Expected Value Tree', status: `${pendingIds.length} Formulated`, icon: Sparkles, color: 'text-cyan-400' },
          { name: '5. Action Gatekeeper', model: 'Dry-run / Live Gate', status: state.mode === 'live' ? 'Live Armed' : 'Dry-run Safe', icon: Zap, color: 'text-emerald-400' },
        ].map((ag) => {
          const Icon = ag.icon
          return (
            <div key={ag.name} className="flex flex-col justify-between rounded-xl border border-line/80 bg-surface/80 p-3 shadow-xs hover:border-line-strong transition-all duration-150">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-fg-2 truncate">{ag.name}</span>
                <Icon size={14} className={ag.color} />
              </div>
              <div className="mt-2">
                <p className="text-xs font-bold text-fg tracking-tight">{ag.status}</p>
                <p className="text-[10px] text-fg-2/70 truncate">{ag.model}</p>
              </div>
            </div>
          )
        })}
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-6 md:grid-cols-12 gap-4">
        <KpiCard
          loading={loading}
          label="Total MRR"
          value={fmtMoney(headline.mrr)}
          delta="+1.8%"
          good
          series={kpiTrends.mrr.series}
          how="Sum of monthly recurring revenue across all 12,480 active subscriptions, from Stripe."
        />
        <KpiCard
          loading={loading}
          label="At-risk accounts"
          value={fmtInt(headline.atRisk)}
          delta="+6.2%"
          good={false}
          series={kpiTrends.atRisk.series}
          how="Accounts with at least a 30% chance of cancelling in the next 90 days (medium or high risk)."
        />
        <KpiCard
          loading={loading}
          label="MRR at risk"
          value={fmtMoney(headline.mrrAtRisk)}
          delta="+4.9%"
          good={false}
          series={kpiTrends.mrrAtRisk.series}
          how="Monthly revenue of each at-risk account multiplied by its chance of cancelling, then added up. Equals 6.1% of total MRR."
        />
        <KpiCard
          loading={loading}
          label="90-day churn"
          value={`${headline.churn90}%`}
          delta="+0.3 pts"
          good={false}
          series={kpiTrends.churn.series}
          how="Share of today's accounts we expect to cancel within 90 days, based on the survival curve on the Churn Risk page."
        />
        <KpiCard
          loading={loading}
          tone="decision"
          label="Pending approvals"
          value={pendingIds.length}
          sub={pendingIds.length ? 'Recommendations waiting for you' : "You're all caught up"}
          to={pendingIds.length ? '/recommendations?tab=pending' : undefined}
          how="Recommendations from the Strategy agent that need a human decision before anything is sent."
        />
        <KpiCard
          loading={loading}
          label="Actions executed (30d)"
          value={headline.actionsExecuted30d}
          sub={
            <span>
              93% success · <span className="num font-semibold text-emerald-400">$6.4k</span> retained
            </span>
          }
          how="Approved actions that ran for real in the last 30 days. Dry runs are not counted."
        />
      </div>

      {/* Main Grid: Decisions + Analytics */}
      <div className="grid grid-cols-12 gap-5">
        <Card className="col-span-12 lg:col-span-8">
          <CardHeader
            title="Needs your decision"
            subtitle="Top pending recommendations, by estimated MRR retained"
            right={
              pendingIds.length > 0 && (
                <Link to="/recommendations?tab=pending" className="inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline">
                  See all {pendingIds.length} <ArrowRight size={12} aria-hidden />
                </Link>
              )
            }
          />
          <div className="space-y-3 px-5 pb-5">
            {loading ? (
              [0, 1, 2].map((i) => <Skeleton key={i} className="h-[92px]" />)
            ) : top.length ? (
              top.map((r) => <RecommendationCard key={r.id} rec={r} compact />)
            ) : (
              <EmptyState
                icon={<PartyPopper size={18} aria-hidden />}
                title="No pending recommendations — you're all caught up"
                body="The next analysis run is scheduled for 06:00 tomorrow. New recommendations will show up here."
                action={
                  <Button size="sm" variant="secondary" onClick={() => navigate('/actions')}>
                    See what's running
                  </Button>
                }
              />
            )}
          </div>
        </Card>

        <Card className="col-span-12 lg:col-span-4">
          <CardHeader title="Risk distribution" subtitle="All 12,480 accounts by chance of cancelling in 90 days" how="Each account gets a probability from the Churn Risk agent. High is 60% or more, medium 30–59%, low under 30%. Thresholds can be changed in Settings." />
          <div className="px-5 pb-5">{loading ? <Skeleton className="h-52" /> : <RiskDistribution data={riskDistribution} />}</div>
        </Card>

        <Card className="col-span-12 lg:col-span-6">
          <CardHeader
            title="Segment health"
            subtitle="At-risk accounts per segment, colored by segment risk level"
            how="Segments come from the User Behavior agent. Bar length is the number of medium- or high-risk accounts. Risk level reflects the segment's share of at-risk accounts and recent trend."
          />
          <div className="px-3 pb-4">{loading ? <Skeleton className="mx-2 h-48" /> : <SegmentHealthBars data={[...segments].sort((a, b) => b.atRisk - a.atRisk)} onSelect={(id) => navigate(`/segments?segment=${id}`)} />}</div>
        </Card>

        <Card className="col-span-12 lg:col-span-6">
          <CardHeader title="Anomaly alerts" subtitle="Unusual changes the agents spotted in the last run" />
          <ul className="px-5 pb-4">
          {anomalies.map((a) => {
            const logRow = a.retryActionId ? state.log.find((l) => l.id === a.retryActionId) : undefined
            const resolved = logRow && logRow.status === 'Executed'
            const icon =
              a.tone === 'good' || resolved ? (
                <TrendingUp size={14} className="text-risk-low" />
              ) : a.tone === 'failed' ? (
                <XCircle size={14} className="text-risk-high" />
              ) : a.tone === 'warn' ? (
                <TriangleAlert size={14} className="text-risk-med" />
              ) : (
                <TrendingDown size={14} className="text-risk-high" />
              )
            return (
              <li key={a.id} className="flex items-start gap-3 border-b border-line py-3 last:border-0">
                <span className={cx('mt-0.5 inline-flex size-6 shrink-0 items-center justify-center rounded-full bg-raised')} aria-hidden>
                  {icon}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-fg">{resolved ? 'Win-back offer resent successfully' : a.title}</p>
                  <p className="mt-0.5 text-xs text-fg-2">{resolved ? '210 accounts reached after retry.' : a.detail}</p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <span className="text-xs text-fg-2">{a.when}</span>
                  {logRow ? (
                    logRow.status === 'Failed' ? (
                      <button type="button" onClick={() => retry(logRow.id)} className="text-xs font-semibold text-accent hover:underline">
                        Retry
                      </button>
                    ) : logRow.status === 'Running' ? (
                      <span className="text-xs text-fg-2">Retrying…</span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-xs text-risk-low">
                        <CheckCircle2 size={12} aria-hidden /> Resolved
                      </span>
                    )
                  ) : (
                    a.link && (
                      <Link to={a.link.to} className="text-xs font-semibold text-accent hover:underline">
                        {a.link.label}
                      </Link>
                    )
                  )}
                </div>
              </li>
            )
          })}
        </ul>
      </Card>

      <Card className="col-span-12">
        <CardHeader
          title="Recent actions"
          subtitle="What the Action agent ran, and early results"
          right={
            <Link to="/actions" className="inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline">
              Open execution log <ArrowRight size={12} aria-hidden />
            </Link>
          }
        />
        <div className="pb-2">
          <DataTable<ActionLogRow>
            caption="Recent actions"
            loading={loading}
            rows={state.log.slice(0, 6)}
            rowKey={(r) => r.id}
            onRowClick={() => navigate('/actions')}
            rowLabel={(r) => `${r.recommendation}, ${r.status}. Open execution log.`}
            columns={[
              { key: 'time', header: 'When', render: (r) => <span className="text-fg-2">{r.time}</span>, width: '120px' },
              { key: 'rec', header: 'Action', render: (r) => <span className="font-medium">{r.recommendation}</span> },
              { key: 'seg', header: 'Segment', render: (r) => <SegmentChip id={r.segment} /> },
              { key: 'type', header: 'Type', render: (r) => <ActionTypeTag type={r.type} /> },
              { key: 'status', header: 'Status', render: (r) => <StatusPill status={r.status} /> },
              { key: 'acc', header: 'Accounts', align: 'right', render: (r) => fmtInt(r.accounts) },
              { key: 'result', header: 'Early result', render: (r) => <span className={cx('text-xs', r.status === 'Failed' ? 'text-risk-high' : 'text-fg-2')}>{r.error ?? r.result}</span> },
            ]}
          />
        </div>
      </Card>
      </div>
    </div>
  )
}
