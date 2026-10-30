import { Link, useParams } from 'react-router'
import { ArrowLeft, CreditCard, LifeBuoy, MousePointerClick, SearchX, Smile, TriangleAlert } from 'lucide-react'
import { accountById, accounts, accountSurvival, levelFor, recommendationById, segmentById, type TimelineEvent } from '@/data/mock'
import { fmtMoney } from '@/lib/format'
import { useApp } from '@/state/AppState'
import { AccountSurvival } from '@/components/charts'
import { ActionTypeTag, Card, CardHeader, EmptyState, RiskBadge, SegmentChip, StatusPill, cx } from '@/components/ui'

const kindIcon: Record<TimelineEvent['kind'], typeof CreditCard> = { usage: MousePointerClick, payment: CreditCard, support: LifeBuoy, csat: Smile }
const kindLabel: Record<TimelineEvent['kind'], string> = { usage: 'Usage', payment: 'Payment', support: 'Support', csat: 'CSAT' }

export default function CustomerDetail() {
  const { id } = useParams()
  const { state } = useApp()
  const a = id ? accountById[id] : undefined

  if (!a) {
    return (
      <Card className="col-span-12">
        <EmptyState
          icon={<SearchX size={18} aria-hidden />}
          title={`We couldn't find account ${id ?? ''}`}
          body="It may have been merged or removed in the latest data sync."
          action={
            <Link to="/churn-risk" className="text-xs font-semibold text-accent hover:underline">
              Back to Churn Risk
            </Link>
          }
        />
      </Card>
    )
  }

  const seg = segmentById[a.segment]
  const level = levelFor(a.risk)
  const similar = accounts.filter((x) => x.segment === a.segment && x.id !== a.id)
  const touched = state.log.filter((l) => l.segment === a.segment)

  return (
    <>
      <div className="col-span-12">
        <Link to="/churn-risk" className="inline-flex items-center gap-1.5 text-xs font-medium text-fg-2 hover:text-fg">
          <ArrowLeft size={14} aria-hidden /> Churn Risk
        </Link>
        <div className="mt-3 flex items-end justify-between gap-6">
          <div>
            <p className="font-mono text-xs text-fg-2">{a.id}</p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight text-fg">{a.name}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-fg-2">
              <SegmentChip id={a.segment} />
              <span>{a.plan} plan</span>
              <span aria-hidden>·</span>
              <span>{a.tenureMonths} months as a customer</span>
              <span aria-hidden>·</span>
              <span className="num font-medium text-fg">{fmtMoney(a.mrr)} MRR</span>
            </div>
          </div>
        </div>
      </div>

      <Card className="col-span-5">
        <CardHeader title="Churn risk" subtitle="From the Churn Risk agent, last run" how="The chance this account cancels within 90 days, with a best guess of when. The range covers the likely timing about 8 times out of 10." />
        <div className="space-y-5 px-5 pb-5">
          <div className="flex items-end gap-6">
            <div>
              <p className={cx('num text-2xl font-semibold', level === 'High' ? 'text-risk-high' : 'text-risk-med')}>{a.risk}%</p>
              <RiskBadge level={level} className="mt-1" />
            </div>
            <div>
              <p className="num text-2xl font-semibold text-fg">~{a.days} days</p>
              <p className="num text-xs text-fg-2">
                likely between {a.daysLo} and {a.daysHi} days
              </p>
            </div>
          </div>
          <div>
            <p className="mb-2 text-xs font-semibold text-fg-2">Main reason: {a.reason}</p>
            <ul className="space-y-1.5">
              {a.drivers.map((d) => (
                <li key={d} className="flex items-start gap-2 text-sm text-fg">
                  <TriangleAlert size={14} className="mt-0.5 shrink-0 text-risk-med" aria-hidden />
                  {d}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Card>

      <Card className="col-span-7">
        <CardHeader title="Chance of staying subscribed" subtitle={`This account vs. the ${seg.name} average`} />
        <div className="px-5 pb-3">
          <AccountSurvival data={accountSurvival(a)} color={seg.color} segmentName={seg.name} />
          <div className="mt-2 flex gap-5 text-xs text-fg-2">
            <span className="flex items-center gap-2">
              <span className="h-0.5 w-5 bg-risk-high" aria-hidden /> This account
            </span>
            <span className="flex items-center gap-2">
              <span className="h-0 w-5 border-t-2 border-dashed" style={{ borderColor: seg.color }} aria-hidden /> {seg.name} average
            </span>
          </div>
        </div>
      </Card>

      <Card className="col-span-7">
        <CardHeader title="Activity timeline" subtitle="Usage, payments, support and satisfaction, newest first" />
        <ol className="relative px-5 pb-5">
          {a.timeline.map((e, i) => {
            const Icon = kindIcon[e.kind]
            return (
              <li key={i} className="relative flex gap-4 pb-4 last:pb-0">
                {i < a.timeline.length - 1 && <span className="absolute top-8 bottom-0 left-[15px] w-px bg-line" aria-hidden />}
                <span className={cx('relative inline-flex size-8 shrink-0 items-center justify-center rounded-full border', e.tone === 'bad' ? 'border-risk-high/40 bg-risk-high/10 text-risk-high' : e.tone === 'good' ? 'border-risk-low/40 bg-risk-low/10 text-risk-low' : 'border-line bg-raised text-fg-2')}>
                  <Icon size={14} aria-hidden />
                </span>
                <div className="pt-1">
                  <p className="text-sm text-fg">{e.text}</p>
                  <p className="text-xs text-fg-2">
                    {kindLabel[e.kind]} · {e.date}
                  </p>
                </div>
              </li>
            )
          })}
        </ol>
      </Card>

      <div className="col-span-5 space-y-6">
        <Card>
          <CardHeader title="Recommendations and actions that touched this account" />
          <ul className="space-y-2 px-5 pb-5">
            {a.recs.map((rid) => {
              const r = recommendationById[rid]
              const st = state.recs[rid].status
              return (
                <li key={rid}>
                  <Link to={`/recommendations?tab=${st}&expand=${rid}`} className="block rounded-md border border-line p-3 hover:border-line-strong">
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-xs text-fg-2">{rid}</span>
                      <ActionTypeTag type={r.type} />
                      <StatusPill status={st === 'pending' ? 'Pending' : st === 'approved' ? 'Approved' : 'Rejected'} />
                    </span>
                    <span className="mt-2 block text-sm font-medium text-fg">{r.title}</span>
                  </Link>
                </li>
              )
            })}
            {touched.slice(0, 2).map((l) => (
              <li key={l.id} className="rounded-md border border-line p-3">
                <span className="flex items-center gap-2">
                  <ActionTypeTag type={l.type} />
                  <StatusPill status={l.status} />
                  <span className="ml-auto text-xs text-fg-2">{l.time}</span>
                </span>
                <span className="mt-2 block text-sm font-medium text-fg">{l.recommendation}</span>
              </li>
            ))}
            {!a.recs.length && !touched.length && <li className="text-sm text-fg-2">No recommendations or actions yet.</li>}
          </ul>
        </Card>

        <Card>
          <CardHeader title="Similar accounts" subtitle={`Other at-risk ${seg.name} accounts`} />
          <ul className="px-2 pb-3">
            {similar.length ? (
              similar.map((s) => (
                <li key={s.id}>
                  <Link to={`/accounts/${s.id}`} className="flex items-center gap-3 rounded-md px-3 py-2.5 hover:bg-raised/60">
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-medium text-fg">{s.name}</span>
                      <span className="font-mono text-xs text-fg-2">{s.id}</span>
                    </span>
                    <RiskBadge level={levelFor(s.risk)} value={s.risk} />
                  </Link>
                </li>
              ))
            ) : (
              <li className="px-3 py-2 text-sm text-fg-2">No other at-risk accounts from this segment in the sample.</li>
            )}
          </ul>
        </Card>
      </div>
    </>
  )
}
