import { Link, useSearchParams } from 'react-router'
import { ArrowRight, Lightbulb, ThumbsDown, ThumbsUp } from 'lucide-react'
import { featureAssumptions, features, recommendations, segmentById } from '@/data/mock'
import { fmtInt, fmtPts, fmtRange } from '@/lib/format'
import { useApp } from '@/state/AppState'
import { ForestPlot, NaiveVsCausalBars } from '@/components/charts'
import { Accordion, Card, CardHeader, PageHeader, SegmentChip, Skeleton, cx } from '@/components/ui'

export default function FeatureImpact() {
  const { state } = useApp()
  const [params, setParams] = useSearchParams()
  const loading = state.lastRun.loading
  const selectedId = params.get('feature') ?? 'scheduled-reports'
  const f = features.find((x) => x.id === selectedId) ?? features[0]
  const linked = recommendations.filter((r) => r.featureId === f.id)
  const promote = features.filter((x) => x.significant)
  const skip = features.filter((x) => !x.significant)

  return (
    <>
      <PageHeader title="Feature Impact" description="Which features actually keep customers, not just which ones engaged customers happen to use." agent="Causal Feature Impact agent" agentStatus={`Completed ${state.lastRun.label}`} />

      <Card className="col-span-8">
        <CardHeader
          title="Effect of each feature on 90-day retention"
          subtitle="Extra accounts out of 100 that stay because they use the feature. Select a row for details."
          how="Each dot is our best estimate. The line shows the likely range. If the line crosses the zero line, we can't rule out that the feature has no effect."
        />
        <div className="px-3 pb-5">{loading ? <Skeleton className="mx-2 h-[380px]" /> : <ForestPlot data={features} selected={f.id} onSelect={(id) => setParams({ feature: id }, { replace: true })} />}</div>
      </Card>

      <Card className="col-span-4">
        <CardHeader title={f.name} subtitle={f.significant ? 'Reliable effect' : 'No reliable effect'} />
        <div className="space-y-5 px-5 pb-5">
          <div>
            <p className={cx('num text-2xl font-semibold', f.significant ? 'text-fg' : 'text-fg-2')}>{fmtPts(f.lift)}</p>
            <p className="num text-xs text-fg-2">Likely range {fmtRange(f.lo, f.hi)} pts on 90-day retention</p>
          </div>
          <p className="text-sm leading-6 text-fg-2">{f.explanation}</p>
          <dl className="num divide-y divide-line rounded-md border border-line text-sm">
            {[
              ['Accounts studied', fmtInt(f.sampleSize)],
              ['Current adoption', f.adoption],
              ['Simple comparison', `+${f.naive} pts`],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3 px-3 py-2">
                <dt className="text-fg-2">{k}</dt>
                <dd className="text-right font-medium text-fg">{v}</dd>
              </div>
            ))}
          </dl>
          <div>
            <p className="mb-2 text-xs font-semibold text-fg-2">Most responsive segments</p>
            {f.responding.length ? (
              <div className="flex flex-wrap gap-2">
                {f.responding.map((s) => (
                  <SegmentChip key={s} id={s} />
                ))}
              </div>
            ) : (
              <p className="text-xs text-fg-2">None stand out.</p>
            )}
          </div>
          {linked.map((r) => (
            <Link key={r.id} to={`/recommendations?tab=${state.recs[r.id].status}&expand=${r.id}`} className="flex items-center gap-3 rounded-md border border-accent/30 bg-accent/8 p-3 hover:border-accent/60">
              <Lightbulb size={16} className="shrink-0 text-accent" aria-hidden />
              <span className="min-w-0 flex-1">
                <span className="block text-xs text-fg-2">Recommendation {r.id} · {segmentById[r.segment].name}</span>
                <span className="block truncate text-sm font-medium text-fg">{r.title}</span>
              </span>
              <ArrowRight size={14} className="text-accent" aria-hidden />
            </Link>
          ))}
        </div>
      </Card>

      <Card className="col-span-12">
        <CardHeader
          title="Looks important vs. actually matters"
          subtitle="Simple comparison of users and non-users, next to the real effect after adjusting for who uses each feature"
          how="The simple comparison just compares retention of users and non-users. The real effect compares users with similar non-users, removing the advantage engaged accounts already had."
        />
        <div className="px-5 pb-5">
          <p className="mb-5 flex items-start gap-2 rounded-md border border-line bg-raised/60 px-3 py-2.5 text-sm text-fg">
            <Lightbulb size={16} className="mt-0.5 shrink-0 text-risk-med" aria-hidden />
            <span>
              <span className="font-semibold">Saved Dashboards looks most important (+11.3) but its real effect is small (+2.1).</span>
              <span className="text-fg-2"> Engaged accounts save dashboards; saving them doesn't make accounts stay. Promote Scheduled Reports instead.</span>
            </span>
          </p>
          {loading ? <Skeleton className="h-[220px]" /> : <NaiveVsCausalBars />}
        </div>
      </Card>

      <Card className="col-span-6">
        <CardHeader title={<span className="flex items-center gap-2"><ThumbsUp size={16} className="text-risk-low" aria-hidden />Worth promoting</span>} subtitle="Reliable, meaningful effect on retention" />
        <ul className="px-5 pb-5">
          {promote.map((x) => (
            <li key={x.id} className="flex items-center justify-between gap-3 border-b border-line py-2.5 last:border-0">
              <button type="button" onClick={() => setParams({ feature: x.id }, { replace: true })} className="text-left text-sm font-medium text-fg hover:text-accent">
                {x.name}
              </button>
              <span className="num text-sm font-semibold text-fg">
                {fmtPts(x.lift)} <span className="text-xs font-normal text-fg-2">({fmtRange(x.lo, x.hi)})</span>
              </span>
            </li>
          ))}
        </ul>
      </Card>
      <Card className="col-span-6">
        <CardHeader title={<span className="flex items-center gap-2"><ThumbsDown size={16} className="text-fg-2" aria-hidden />Don't prioritize</span>} subtitle="No effect we can tell apart from zero" />
        <ul className="px-5 pb-5">
          {skip.map((x) => (
            <li key={x.id} className="flex items-center justify-between gap-3 border-b border-line py-2.5 last:border-0">
              <button type="button" onClick={() => setParams({ feature: x.id }, { replace: true })} className="text-left text-sm font-medium text-fg-2 hover:text-accent">
                {x.name}
              </button>
              <span className="num text-sm text-fg-2">
                {fmtPts(x.lift)} <span className="text-xs">({fmtRange(x.lo, x.hi)})</span>
              </span>
            </li>
          ))}
        </ul>
      </Card>

      <Accordion className="col-span-12" title="Assumptions behind these numbers" subtitle="What has to be true for the effects to hold">
        <ol className="list-decimal space-y-2 pl-5 text-sm text-fg-2">
          {featureAssumptions.map((a) => (
            <li key={a}>{a}</li>
          ))}
        </ol>
      </Accordion>
    </>
  )
}
