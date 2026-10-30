import { useState } from 'react'
import { useNavigate } from 'react-router'
import { SearchX } from 'lucide-react'
import { accounts, churnReasons, expectedCancellations, headline, levelFor, segments, survival, type Account } from '@/data/mock'
import { fmtInt, fmtMoney } from '@/lib/format'
import { useApp } from '@/state/AppState'
import DataTable from '@/components/DataTable'
import { Donut, SurvivalCurve } from '@/components/charts'
import { Accordion, Button, Card, CardHeader, EmptyState, FilterChip, PageHeader, RiskBadge, SegmentChip, Select, Skeleton, StatTile } from '@/components/ui'

export default function ChurnRisk() {
  const { state, setSegment } = useApp()
  const navigate = useNavigate()
  const loading = state.lastRun.loading
  const [reason, setReason] = useState<'all' | 'Dissatisfaction' | 'Payment'>('all')
  const [level, setLevel] = useState<'all' | 'High' | 'Medium'>('all')

  const rows = accounts.filter(
    (a) => (state.segmentFilter === 'all' || a.segment === state.segmentFilter) && (reason === 'all' || a.reason === reason) && (level === 'all' || levelFor(a.risk) === level),
  )
  const filtered = reason !== 'all' || level !== 'all' || state.segmentFilter !== 'all'

  return (
    <>
      <PageHeader title="Churn Risk" description="Who is likely to cancel, roughly when, and why." agent="Churn Risk agent" agentStatus={`Completed ${state.lastRun.label}`} />

      {expectedCancellations.map((e) => (
        <StatTile
          key={e.window}
          loading={loading}
          label={`Expected cancellations · ${e.window.toLowerCase()}`}
          value={fmtInt(e.accounts)}
          sub={`${((e.accounts / headline.accounts) * 100).toFixed(1)}% of ${fmtInt(headline.accounts)} accounts`}
          how="Sum of every account's probability of cancelling within the window. It is an expected count, not a list of named accounts."
        />
      ))}
      <StatTile
        loading={loading}
        tone="high"
        label="MRR at risk"
        value={fmtMoney(headline.mrrAtRisk)}
        sub={`${headline.mrrAtRiskShare}% of ${fmtMoney(headline.mrr)} total MRR`}
        how="Each at-risk account's monthly revenue multiplied by its chance of cancelling in 90 days, added up."
      />

      <Card className="col-span-8">
        <CardHeader
          title="How many accounts stay subscribed over time"
          subtitle="Share of today's accounts still subscribed after N days"
          how="A survival curve. It starts at 100% and steps down as accounts are expected to cancel. Steeper drops mean faster churn."
        />
        <div className="px-5 pb-5">{loading ? <Skeleton className="h-[330px]" /> : <SurvivalCurve data={survival} />}</div>
      </Card>

      <Card className="col-span-4">
        <CardHeader title="Why accounts are likely to cancel" subtitle="Predicted cancellations by main reason" how="For each at-risk account the model names the signal that contributes most to its risk. Signals are grouped into two reasons." />
        <div className="px-5 pb-5">
          {loading ? (
            <Skeleton className="h-[300px]" />
          ) : (
            <Donut
              data={[
                { label: 'Dissatisfaction', value: churnReasons[0].share, color: '#8FA3BF', detail: churnReasons[0].detail },
                { label: 'Payment', value: churnReasons[1].share, color: '#56657A', detail: churnReasons[1].detail },
              ]}
              center={
                <>
                  <span className="num text-2xl font-semibold text-fg">{fmtInt(headline.atRisk)}</span>
                  <span className="text-xs text-fg-2">at-risk accounts</span>
                </>
              }
            />
          )}
        </div>
      </Card>

      <Card className="col-span-12">
        <CardHeader title="At-risk accounts" subtitle="Highest-risk accounts first. Select a row to see the full story." />
        <div className="flex flex-wrap items-center gap-2 px-5 pb-3">
          <Select
            label="Segment"
            value={state.segmentFilter}
            onChange={(v) => setSegment(v as typeof state.segmentFilter)}
            options={[{ value: 'all', label: 'All segments' }, ...segments.map((s) => ({ value: s.id, label: s.name }))]}
          />
          <span className="mx-1 h-5 w-px bg-line" aria-hidden />
          <span className="text-xs text-fg-2">Reason</span>
          {(['all', 'Dissatisfaction', 'Payment'] as const).map((r) => (
            <FilterChip key={r} active={reason === r} onClick={() => setReason(r)}>
              {r === 'all' ? 'All' : r}
            </FilterChip>
          ))}
          <span className="mx-1 h-5 w-px bg-line" aria-hidden />
          <span className="text-xs text-fg-2">Risk</span>
          {(['all', 'High', 'Medium'] as const).map((l) => (
            <FilterChip key={l} active={level === l} onClick={() => setLevel(l)}>
              {l === 'all' ? 'All' : l}
            </FilterChip>
          ))}
          {filtered && (
            <Button
              size="sm"
              variant="ghost"
              className="ml-auto"
              onClick={() => {
                setReason('all')
                setLevel('all')
                setSegment('all')
              }}
            >
              Clear filters
            </Button>
          )}
        </div>
        <DataTable<Account>
          caption="At-risk accounts"
          loading={loading}
          rows={rows}
          rowKey={(r) => r.id}
          onRowClick={(r) => navigate(`/accounts/${r.id}`)}
          rowLabel={(r) => `Open ${r.name}`}
          defaultSort={{ key: 'risk', dir: 'desc' }}
          empty={<EmptyState icon={<SearchX size={18} aria-hidden />} title="No accounts match these filters" body="Try a different segment or reason." />}
          columns={[
            {
              key: 'name',
              header: 'Account',
              render: (r) => (
                <span>
                  <span className="block font-medium">{r.name}</span>
                  <span className="font-mono text-xs text-fg-2">{r.id}</span>
                </span>
              ),
            },
            { key: 'seg', header: 'Segment', render: (r) => <SegmentChip id={r.segment} /> },
            { key: 'plan', header: 'Plan', render: (r) => <span className="text-fg-2">{r.plan}</span> },
            { key: 'mrr', header: 'MRR', align: 'right', sortValue: (r) => r.mrr, render: (r) => fmtMoney(r.mrr) },
            { key: 'risk', header: 'Chance of cancelling', sortValue: (r) => r.risk, render: (r) => <RiskBadge level={levelFor(r.risk)} value={r.risk} /> },
            {
              key: 'days',
              header: 'Likely within',
              align: 'right',
              sortValue: (r) => -r.days,
              render: (r) => (
                <span>
                  ~{r.days} days <span className="block text-xs text-fg-2">{r.daysLo}–{r.daysHi} days</span>
                </span>
              ),
            },
            { key: 'reason', header: 'Main reason', render: (r) => <span className="text-fg-2">{r.reason}</span> },
            { key: 'driver', header: 'Top signal', render: (r) => <span className="line-clamp-1 max-w-[260px] text-xs text-fg-2">{r.drivers[0]}</span> },
          ]}
        />
        <p className="border-t border-line px-5 py-3 text-xs text-fg-2">
          Showing {rows.length} of {fmtInt(headline.atRisk)} at-risk accounts (sample). Export the full list from the top bar.
        </p>
      </Card>

      <Accordion className="col-span-12" title="Model quality: can we trust these numbers?" subtitle="How well past predictions matched what actually happened">
        <div className="grid grid-cols-3 gap-6 text-sm text-fg-2">
          <div>
            <p className="font-semibold text-fg">Predictions match reality</p>
            <p className="mt-1">When we said an account was 70% likely to cancel, about 68% of those accounts did. Across all risk levels, predicted and actual rates stay within 3 points.</p>
          </div>
          <div>
            <p className="font-semibold text-fg">We catch most cancellations early</p>
            <p className="mt-1">Of the accounts that cancelled last quarter, 81% were flagged as medium or high risk at least 30 days before.</p>
          </div>
          <div>
            <p className="font-semibold text-fg">Timing is a range, not a date</p>
            <p className="mt-1">"~38 days" is our best guess; the true date falls inside the shown range about 8 times out of 10.</p>
          </div>
        </div>
      </Accordion>
    </>
  )
}
