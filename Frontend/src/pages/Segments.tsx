import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { ArrowRight, Flag } from 'lucide-react'
import { accounts, headline, recommendations, segmentById, segmentMethod, segments, type Segment, type SegmentId } from '@/data/mock'
import { fmtInt, fmtMoney, fmtPts } from '@/lib/format'
import { useApp } from '@/state/AppState'
import DataTable from '@/components/DataTable'
import { Drawer } from '@/components/Overlay'
import { BubbleClusterMap, DivergingBars, EngagementTrend, Sparkline } from '@/components/charts'
import { Accordion, ActionTypeTag, Card, CardHeader, PageHeader, RiskBadge, Skeleton, StatusPill, cx } from '@/components/ui'

export default function Segments() {
  const { state } = useApp()
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const drawerId = params.get('segment') as SegmentId | null
  const [selected, setSelected] = useState<SegmentId>(drawerId && segmentById[drawerId] ? drawerId : 'smb')
  const loading = state.lastRun.loading
  const rows = state.segmentFilter === 'all' ? segments : segments.filter((s) => s.id === state.segmentFilter)
  const sel = segmentById[selected]
  const drawerSeg = drawerId ? segmentById[drawerId] : undefined

  const openDrawer = (id: SegmentId) => {
    setSelected(id)
    setParams({ segment: id })
  }

  return (
    <>
      <PageHeader title="Segments" description="Groups of accounts that behave alike, and how each group's health is changing." agent="User Behavior agent" agentStatus={`Completed ${state.lastRun.label}`} />

      <Card className="col-span-12">
        <CardHeader title="All segments" subtitle={`${fmtInt(headline.accounts)} accounts in five behavior groups. Select a row for details.`} />
        <DataTable<Segment>
          caption="Segments"
          loading={loading}
          rows={rows}
          rowKey={(r) => r.id}
          onRowClick={(r) => openDrawer(r.id)}
          rowLabel={(r) => `Open ${r.name} details`}
          defaultSort={{ key: 'accounts', dir: 'desc' }}
          columns={[
            {
              key: 'name',
              header: 'Segment',
              sortValue: (r) => r.name,
              render: (r) => (
                <span className="flex items-center gap-2.5 font-medium">
                  <span className="size-2.5 rounded-full" style={{ background: r.color }} aria-hidden />
                  {r.name}
                </span>
              ),
            },
            { key: 'accounts', header: 'Accounts', align: 'right', sortValue: (r) => r.accounts, render: (r) => fmtInt(r.accounts) },
            { key: 'share', header: 'Share', align: 'right', sortValue: (r) => r.accounts, render: (r) => `${((r.accounts / headline.accounts) * 100).toFixed(1)}%` },
            { key: 'mrr', header: 'Avg. MRR', align: 'right', sortValue: (r) => r.avgMrr, render: (r) => fmtMoney(r.avgMrr) },
            { key: 'atrisk', header: 'At-risk accounts', align: 'right', sortValue: (r) => r.atRisk, render: (r) => fmtInt(r.atRisk) },
            {
              key: 'risk',
              header: 'Avg. risk',
              sortValue: (r) => r.avgRisk,
              render: (r) => (
                <span className="flex items-center gap-2">
                  <RiskBadge level={r.riskLevel} />
                  <span className="num text-xs text-fg-2">{r.avgRisk}% avg.</span>
                </span>
              ),
            },
            {
              key: 'trend',
              header: 'Risk trend (12 wk)',
              sortValue: (r) => r.riskTrend,
              render: (r) => (
                <span className="flex items-center gap-3">
                  <Sparkline data={r.riskSeries} color={r.riskTrend > 0.5 ? 'var(--risk-high)' : r.riskTrend < 0 ? 'var(--risk-low)' : 'var(--text-2)'} width={88} height={24} label={`${r.name} risk trend`} />
                  <span className={cx('num text-xs font-medium', r.riskTrend > 0.5 ? 'text-risk-high' : r.riskTrend < 0 ? 'text-risk-low' : 'text-fg-2')}>{r.riskTrend === 0 ? 'flat' : fmtPts(r.riskTrend)}</span>
                </span>
              ),
            },
          ]}
        />
      </Card>

      <Card className="col-span-7">
        <CardHeader title="Segment map" subtitle="Where each group sits on product depth and engagement. Bubble size = accounts." how="Each account gets a product-depth score (share of key features used) and an engagement score (how often people log in). Bubbles sit at each segment's average." />
        <div className="px-5 pb-5">{loading ? <Skeleton className="h-[320px]" /> : <BubbleClusterMap data={segments} selected={selected} onSelect={setSelected} />}</div>
      </Card>

      <Card className="col-span-5">
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <span className="size-2.5 rounded-full" style={{ background: sel.color }} aria-hidden />
              {sel.name}
            </span>
          }
          subtitle="Behavior compared with the average account"
          right={
            <button type="button" onClick={() => openDrawer(sel.id)} className="text-xs font-semibold text-accent hover:underline">
              Details
            </button>
          }
        />
        <div className="px-5 pb-5">
          <p className="mb-4 text-sm text-fg-2">{sel.summary}</p>
          <div className="num mb-5 grid grid-cols-3 gap-3">
            {[
              ['Accounts', fmtInt(sel.accounts)],
              ['At risk', fmtInt(sel.atRisk)],
              ['MRR at risk', fmtMoney(sel.mrrAtRisk)],
            ].map(([l, v]) => (
              <div key={l} className="rounded-md bg-raised px-3 py-2">
                <p className="text-xs text-fg-2">{l}</p>
                <p className="text-sm font-semibold text-fg">{v}</p>
              </div>
            ))}
          </div>
          {loading ? <Skeleton className="h-40" /> : <DivergingBars data={sel.profile} color={sel.color} />}
        </div>
      </Card>

      <Card className="col-span-12">
        <CardHeader title="Engagement over 12 weeks" subtitle="Average sessions per account per week" how="Count of distinct days with at least one session, averaged across accounts in the segment, per week." />
        <div className="px-5 pb-5">{loading ? <Skeleton className="h-[300px]" /> : <EngagementTrend data={segments} />}</div>
      </Card>

      <Accordion className="col-span-12" title="Method: how segments are formed" subtitle="Plain-English explanation of the grouping">
        <ul className="space-y-2 text-sm text-fg-2">
          {segmentMethod.map((m) => (
            <li key={m} className="flex gap-2">
              <span className="mt-2 size-1 shrink-0 rounded-full bg-fg-2" aria-hidden />
              {m}
            </li>
          ))}
        </ul>
      </Accordion>

      <Drawer
        open={!!drawerSeg}
        onClose={() => setParams({})}
        title={
          drawerSeg && (
            <span className="flex items-center gap-2">
              <span className="size-3 rounded-full" style={{ background: drawerSeg.color }} aria-hidden />
              {drawerSeg.name}
            </span>
          )
        }
        subtitle={drawerSeg?.summary}
      >
        {drawerSeg && (
          <div className="space-y-6">
            <div className="num grid grid-cols-2 gap-3">
              {[
                ['Accounts', fmtInt(drawerSeg.accounts)],
                ['Avg. MRR', fmtMoney(drawerSeg.avgMrr)],
                ['At-risk accounts', fmtInt(drawerSeg.atRisk)],
                ['MRR at risk', fmtMoney(drawerSeg.mrrAtRisk)],
              ].map(([l, v]) => (
                <div key={l} className="rounded-md border border-line bg-raised/60 px-3 py-2.5">
                  <p className="text-xs text-fg-2">{l}</p>
                  <p className="text-base font-semibold text-fg">{v}</p>
                </div>
              ))}
              <div className="col-span-2 flex items-center gap-2 text-xs text-fg-2">
                <RiskBadge level={drawerSeg.riskLevel} /> Avg. churn probability {drawerSeg.avgRisk}% · {drawerSeg.riskTrend === 0 ? 'flat' : fmtPts(drawerSeg.riskTrend)} in 30 days
              </div>
            </div>

            <section>
              <h3 className="mb-2 text-sm font-semibold text-fg">Flags</h3>
              <ul className="space-y-1.5">
                {drawerSeg.flags.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-fg-2">
                    <Flag size={14} className="mt-0.5 shrink-0 text-risk-med" aria-hidden />
                    {f}
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <h3 className="mb-2 text-sm font-semibold text-fg">Highest-risk members</h3>
              {accounts.filter((a) => a.segment === drawerSeg.id).length ? (
                <ul className="divide-y divide-line rounded-md border border-line">
                  {accounts
                    .filter((a) => a.segment === drawerSeg.id)
                    .sort((a, b) => b.risk - a.risk)
                    .map((a) => (
                      <li key={a.id}>
                        <Link to={`/accounts/${a.id}`} className="flex items-center gap-3 px-3 py-2.5 hover:bg-raised/60">
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium text-fg">{a.name}</span>
                            <span className="font-mono text-xs text-fg-2">{a.id}</span>
                          </span>
                          <span className="num text-xs text-fg-2">{fmtMoney(a.mrr)}/mo</span>
                          <RiskBadge level={a.risk >= 60 ? 'High' : 'Medium'} value={a.risk} />
                        </Link>
                      </li>
                    ))}
                </ul>
              ) : (
                <p className="text-sm text-fg-2">No high-risk members in the sample.</p>
              )}
              <button type="button" onClick={() => navigate('/churn-risk')} className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline">
                See all at-risk accounts <ArrowRight size={12} aria-hidden />
              </button>
            </section>

            <section>
              <h3 className="mb-2 text-sm font-semibold text-fg">Linked recommendations</h3>
              {recommendations.filter((r) => r.segment === drawerSeg.id).length ? (
                <ul className="space-y-2">
                  {recommendations
                    .filter((r) => r.segment === drawerSeg.id)
                    .map((r) => {
                      const st = state.recs[r.id].status
                      return (
                        <li key={r.id}>
                          <Link to={`/recommendations?tab=${st}&expand=${r.id}`} className="block rounded-md border border-line p-3 hover:border-line-strong">
                            <span className="flex items-center gap-2">
                              <ActionTypeTag type={r.type} />
                              <StatusPill status={st === 'pending' ? 'Pending' : st === 'approved' ? 'Approved' : 'Rejected'} />
                              <span className="num ml-auto text-xs text-fg-2">{fmtMoney(r.mrrRetained)} est.</span>
                            </span>
                            <span className="mt-2 block text-sm font-medium text-fg">{r.title}</span>
                          </Link>
                        </li>
                      )
                    })}
                </ul>
              ) : (
                <p className="text-sm text-fg-2">No recommendations for this segment in the latest run.</p>
              )}
            </section>
          </div>
        )}
      </Drawer>
    </>
  )
}
