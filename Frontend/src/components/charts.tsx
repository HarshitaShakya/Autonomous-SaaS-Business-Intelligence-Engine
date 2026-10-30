import { useState, type ReactNode } from 'react'
import { CartesianGrid, Line, LineChart, Pie, PieChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Feature, RiskLevel, Segment, SegmentId } from '@/data/mock'
import { features as allFeatures, segmentById, segments } from '@/data/mock'
import { fmtInt, fmtPts, fmtRange } from '@/lib/format'
import { RiskIcon, cx } from './ui'

const axisTick = { fill: 'var(--text-2)', fontSize: 12 }
const tooltipProps = {
  contentStyle: { background: 'var(--raised)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12, color: 'var(--text)' },
  labelStyle: { color: 'var(--text)', fontWeight: 600, marginBottom: 4 },
  itemStyle: { color: 'var(--text-2)', padding: 0 },
  cursor: { stroke: 'var(--border-strong)', strokeDasharray: '3 3' },
}

/** Visually hidden data table fallback for screen readers. */
function SrTable({ caption, head, rows }: { caption: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <table className="sr-only-table">
      <caption>{caption}</caption>
      <thead>
        <tr>
          {head.map((h) => (
            <th key={h}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>
            {r.map((c, j) => (
              <td key={j}>{c}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

/* Sparkline ---------------------------------------------------------- */

export function Sparkline({ data, color = 'var(--text-2)', width = 96, height = 32, label }: { data: number[]; color?: string; width?: number; height?: number; label?: string }) {
  const min = Math.min(...data)
  const max = Math.max(...data)
  const span = max - min || 1
  const pts = data.map((v, i) => [(i / (data.length - 1)) * (width - 6) + 3, height - 4 - ((v - min) / span) * (height - 8)])
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ')
  const last = pts[pts.length - 1]
  const gradId = `spark-grad-${Math.abs(pts[0]?.[1] || 0).toFixed(0)}-${width}`

  return (
    <svg width={width} height={height} role="img" aria-label={label ?? 'Trend over the last 12 weeks'} className="shrink-0 overflow-visible">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.25} />
          <stop offset="100%" stopColor={color} stopOpacity={0.0} />
        </linearGradient>
      </defs>
      <path d={`${d} L${last[0]},${height} L${pts[0][0]},${height} Z`} fill={`url(#${gradId})`} />
      <path d={d} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={last[0]} cy={last[1]} r={2.75} fill={color} />
      <circle cx={last[0]} cy={last[1]} r={5.5} fill={color} opacity={0.2} />
    </svg>
  )
}

/* Risk distribution -------------------------------------------------- */

const riskColor: Record<RiskLevel, string> = { High: 'var(--risk-high)', Medium: 'var(--risk-med)', Low: 'var(--risk-low)' }

export function RiskDistribution({ data }: { data: { level: RiskLevel; accounts: number; range: string }[] }) {
  const total = data.reduce((s, d) => s + d.accounts, 0)
  const atRisk = data.filter((d) => d.level !== 'Low').reduce((s, d) => s + d.accounts, 0)
  return (
    <div>
      <div className="flex h-3 overflow-hidden rounded-full bg-raised" aria-hidden>
        {data.map((d) => (
          <span key={d.level} style={{ width: `${Math.max((d.accounts / total) * 100, 1.5)}%`, background: riskColor[d.level] }} />
        ))}
      </div>
      <ul className="mt-5 space-y-4">
        {data.map((d) => {
          const pct = (d.accounts / total) * 100
          return (
            <li key={d.level} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1.5">
              <span className="flex items-center gap-1.5 text-sm font-medium" style={{ color: riskColor[d.level] }}>
                <RiskIcon level={d.level} size={14} />
                <span>{d.level} risk</span>
                <span className="text-xs font-normal text-fg-2">{d.range}</span>
              </span>
              <span className="num text-sm font-semibold text-fg">
                {fmtInt(d.accounts)} <span className="text-xs font-normal text-fg-2">· {pct.toFixed(1)}%</span>
              </span>
              <span className="col-span-2 block h-1.5 rounded-full bg-raised">
                <span className="block h-full rounded-full" style={{ width: `${Math.max(pct, 1)}%`, background: riskColor[d.level] }} />
              </span>
            </li>
          )
        })}
      </ul>
      <p className="mt-5 border-t border-line pt-3 text-xs text-fg-2">
        <span className="num font-semibold text-fg">{fmtInt(atRisk)}</span> accounts are at medium or high risk, out of <span className="num">{fmtInt(total)}</span>.
      </p>
    </div>
  )
}

/* Segment health bars ------------------------------------------------ */

export function SegmentHealthBars({ data, onSelect }: { data: Segment[]; onSelect?: (id: SegmentId) => void }) {
  const max = Math.max(...data.map((d) => d.atRisk))
  return (
    <ul className="space-y-1" aria-label="At-risk accounts by segment">
      {data.map((s) => (
        <li key={s.id}>
          <button
            type="button"
            onClick={() => onSelect?.(s.id)}
            className="grid w-full grid-cols-[168px_1fr_92px] items-center gap-3 rounded-md px-2 py-2 text-left hover:bg-raised/60"
            aria-label={`${s.name}: ${s.atRisk} at-risk accounts, ${s.riskLevel} risk. Open segment.`}
          >
            <span className="flex min-w-0 items-center gap-2 text-sm text-fg">
              <span className="inline-block size-2 shrink-0 rounded-full" style={{ background: s.color }} aria-hidden />
              <span className="truncate">{s.name}</span>
            </span>
            <span className="flex items-center gap-2">
              <span className="h-2 rounded-full" style={{ width: `${(s.atRisk / max) * 100}%`, background: riskColor[s.riskLevel], opacity: 0.85 }} />
              <span className="num text-xs font-semibold text-fg">{fmtInt(s.atRisk)}</span>
            </span>
            <span className="flex items-center justify-end gap-1 text-xs font-medium" style={{ color: riskColor[s.riskLevel] }}>
              <RiskIcon level={s.riskLevel} />
              {s.riskLevel}
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}

/* Bubble cluster map ------------------------------------------------- */

export function BubbleClusterMap({ data, selected, onSelect }: { data: Segment[]; selected: SegmentId; onSelect: (id: SegmentId) => void }) {
  const [hover, setHover] = useState<SegmentId | null>(null)
  const W = 680
  const H = 340
  const pad = { l: 48, r: 24, t: 20, b: 44 }
  const maxAcc = Math.max(...data.map((d) => d.accounts))
  const x = (v: number) => pad.l + (v / 100) * (W - pad.l - pad.r)
  const y = (v: number) => H - pad.b - (v / 100) * (H - pad.t - pad.b)
  const r = (n: number) => 18 + Math.sqrt(n / maxAcc) * 42
  const active = hover ?? selected
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="group" aria-label="Segments plotted by product depth and engagement frequency. Bubble size is number of accounts.">
        {[0, 25, 50, 75, 100].map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={pad.t} y2={H - pad.b} stroke="var(--border)" strokeDasharray={t === 50 ? '0' : '2 4'} opacity={t === 50 ? 0.9 : 0.6} />
            <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="var(--border)" strokeDasharray={t === 50 ? '0' : '2 4'} opacity={t === 50 ? 0.9 : 0.6} />
          </g>
        ))}
        <text x={(W + pad.l) / 2} y={H - 10} textAnchor="middle" fontSize={12} fill="var(--text-2)">
          Product depth (features used) →
        </text>
        <text x={14} y={(H - pad.b + pad.t) / 2} textAnchor="middle" fontSize={12} fill="var(--text-2)" transform={`rotate(-90 14 ${(H - pad.b + pad.t) / 2})`}>
          Engagement frequency →
        </text>
        {data.map((s) => {
          const cx0 = x(s.position.depth)
          const cy0 = y(s.position.frequency)
          const rad = r(s.accounts)
          const isSel = s.id === selected
          const dim = active && active !== s.id
          return (
            <g
              key={s.id}
              role="button"
              tabIndex={0}
              aria-pressed={isSel}
              aria-label={`${s.name}, ${fmtInt(s.accounts)} accounts, ${s.riskLevel} risk`}
              onClick={() => onSelect(s.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelect(s.id)
                }
              }}
              onMouseEnter={() => setHover(s.id)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(s.id)}
              onBlur={() => setHover(null)}
              className="cursor-pointer outline-none"
              style={{ opacity: dim ? 0.45 : 1, transition: 'opacity 120ms' }}
            >
              <circle cx={cx0} cy={cy0} r={rad} fill={s.color} fillOpacity={0.22} stroke={s.color} strokeWidth={isSel ? 2.5 : 1.25} />
              {isSel && <circle cx={cx0} cy={cy0} r={rad + 5} fill="none" stroke={s.color} strokeOpacity={0.5} strokeDasharray="3 3" />}
              <text x={cx0} y={cy0 - 2} textAnchor="middle" fontSize={12} fontWeight={600} fill="var(--text)">
                {s.name.split(' ')[0]}
              </text>
              <text x={cx0} y={cy0 + 13} textAnchor="middle" fontSize={11} fill="var(--text-2)" className="num">
                {fmtInt(s.accounts)}
              </text>
            </g>
          )
        })}
      </svg>
      {hover && (
        <div className="pointer-events-none absolute top-3 right-3 w-56 rounded-md border border-line bg-raised p-3 text-xs shadow-[var(--shadow)]">
          <p className="flex items-center gap-2 text-sm font-semibold text-fg">
            <span className="size-2 rounded-full" style={{ background: segmentById[hover].color }} />
            {segmentById[hover].name}
          </p>
          <dl className="num mt-2 grid grid-cols-2 gap-y-1 text-fg-2">
            <dt>Accounts</dt>
            <dd className="text-right text-fg">{fmtInt(segmentById[hover].accounts)}</dd>
            <dt>At risk</dt>
            <dd className="text-right text-fg">{fmtInt(segmentById[hover].atRisk)}</dd>
            <dt>Avg. churn probability</dt>
            <dd className="text-right text-fg">{segmentById[hover].avgRisk}%</dd>
          </dl>
        </div>
      )}
    </div>
  )
}

/* Diverging bars ----------------------------------------------------- */

export function DivergingBars({ data, color }: { data: { metric: string; delta: number }[]; color: string }) {
  const cap = 100
  return (
    <div>
      <div className="mb-2 grid grid-cols-[150px_1fr] text-xs text-fg-2">
        <span />
        <span className="flex justify-between">
          <span>Below average</span>
          <span>Above average</span>
        </span>
      </div>
      <ul className="space-y-2.5">
        {data.map((d) => {
          const w = (Math.min(Math.abs(d.delta), cap) / cap) * 50
          return (
            <li key={d.metric} className="grid grid-cols-[150px_1fr] items-center gap-0">
              <span className="pr-3 text-xs text-fg">{d.metric}</span>
              <span className="relative block h-6">
                <span className="absolute top-0 bottom-0 left-1/2 w-px bg-line-strong" aria-hidden />
                <span
                  className="absolute top-1/2 h-3.5 -translate-y-1/2 rounded-sm"
                  style={{
                    background: color,
                    opacity: d.delta < 0 ? 0.55 : 0.9,
                    width: `${w}%`,
                    left: d.delta < 0 ? `${50 - w}%` : '50%',
                  }}
                  aria-hidden
                />
                <span
                  className="num absolute top-1/2 -translate-y-1/2 text-xs font-semibold text-fg"
                  style={d.delta < 0 ? { right: `${50 + w + 1.5}%` } : { left: `${50 + w + 1.5}%` }}
                >
                  {d.delta > 0 ? '+' : '−'}
                  {Math.abs(d.delta)}%{Math.abs(d.delta) > cap ? '' : ''}
                </span>
              </span>
            </li>
          )
        })}
      </ul>
      <SrTable caption="Segment behavior compared with overall average" head={['Metric', 'Difference']} rows={data.map((d) => [d.metric, `${d.delta}%`])} />
    </div>
  )
}

/* Engagement trend --------------------------------------------------- */

export function EngagementTrend({ data }: { data: Segment[] }) {
  const rows = Array.from({ length: 12 }, (_, i) => {
    const row: Record<string, number | string> = { week: `W${i + 1}` }
    for (const s of data) row[s.id] = s.engagement[i]
    return row
  })
  return (
    <div className="h-[300px] w-full">
      <ResponsiveContainer>
        <LineChart data={rows} margin={{ top: 24, right: 150, bottom: 4, left: -8 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="2 4" />
          <XAxis dataKey="week" tick={axisTick} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
          <YAxis tick={axisTick} tickLine={false} axisLine={false} domain={[0, 13]} width={40} />
          <Tooltip {...tooltipProps} formatter={(v, n) => [`${v} sessions/wk`, segmentById[n as SegmentId]?.name ?? n]} />
          <ReferenceLine
            x="W8"
            stroke="var(--risk-high)"
            strokeDasharray="4 4"
            label={{ value: 'SMB: Scheduled Reports −23%, sessions −18%', position: 'insideTopLeft', fill: 'var(--risk-high)', fontSize: 12, dy: -20, dx: 6 }}
          />
          {data.map((s) => (
            <Line
              key={s.id}
              type="monotone"
              dataKey={s.id}
              stroke={s.color}
              strokeWidth={s.id === 'smb' ? 3 : 1.75}
              dot={false}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
              label={(p: { x?: number | string; y?: number | string; index?: number }) =>
                p.index === 11 ? (
                  <text key={s.id} x={Number(p.x) + 8} y={Number(p.y) + 4} fontSize={12} fill={s.color} fontWeight={s.id === 'smb' ? 600 : 500}>
                    {s.name} · {s.engagement[11]}
                  </text>
                ) : (
                  <g key={`${s.id}-${p.index}`} />
                )
              }
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <SrTable caption="Weekly sessions per account by segment" head={['Segment', ...rows.map((r) => String(r.week))]} rows={data.map((s) => [s.name, ...s.engagement])} />
    </div>
  )
}

/* Survival curve ----------------------------------------------------- */

export function SurvivalCurve({ data }: { data: Record<string, number>[] }) {
  const [shown, setShown] = useState<SegmentId[]>(['smb', 'starters'])
  const toggle = (id: SegmentId) => setShown((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2" role="group" aria-label="Compare segments">
        <span className="inline-flex h-7 items-center gap-1.5 rounded-full border border-line bg-raised px-3 text-xs font-semibold text-fg">
          <span className="h-0.5 w-4 rounded bg-fg" aria-hidden />
          All accounts
        </span>
        {segments.map((s) => {
          const on = shown.includes(s.id)
          return (
            <button
              key={s.id}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(s.id)}
              className={cx('inline-flex h-7 items-center gap-1.5 rounded-full border px-3 text-xs font-medium', on ? 'border-line-strong bg-raised text-fg' : 'border-line text-fg-2 hover:text-fg')}
            >
              <span className="h-0.5 w-4 rounded" style={{ background: on ? s.color : 'var(--border-strong)' }} aria-hidden />
              {s.name}
            </button>
          )
        })}
      </div>
      <div className="h-[280px] w-full">
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 16, right: 24, bottom: 4, left: -8 }}>
            <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="2 4" />
            <XAxis dataKey="day" type="number" domain={[0, 180]} ticks={[0, 30, 60, 90, 120, 150, 180]} tick={axisTick} tickLine={false} axisLine={{ stroke: 'var(--border)' }} tickFormatter={(v) => `${v}d`} />
            <YAxis domain={[80, 100]} tick={axisTick} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} width={48} />
            <Tooltip {...tooltipProps} labelFormatter={(d) => `Day ${d}`} formatter={(v, n) => [`${v}% still subscribed`, n === 'overall' ? 'All accounts' : segmentById[n as SegmentId]?.name]} />
            {[30, 60, 90].map((d) => (
              <ReferenceLine key={d} x={d} stroke="var(--border-strong)" strokeDasharray="3 3" label={{ value: `${d} days`, position: 'top', fill: 'var(--text-2)', fontSize: 11 }} />
            ))}
            {segments
              .filter((s) => shown.includes(s.id))
              .map((s) => (
                <Line key={s.id} type="stepAfter" dataKey={s.id} stroke={s.color} strokeWidth={1.75} dot={false} isAnimationActive={false} />
              ))}
            <Line type="stepAfter" dataKey="overall" stroke="var(--text)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-xs text-fg-2">
        At 90 days, <span className="num font-semibold text-fg">93.6%</span> of all accounts are still subscribed (6.4% churn). Low-Engagement Starters and SMB Self-Serve drop fastest.
      </p>
      <SrTable caption="Share of accounts still subscribed by day" head={['Day', 'All', ...segments.map((s) => s.name)]} rows={data.map((r) => [r.day, r.overall, ...segments.map((s) => r[s.id])])} />
    </div>
  )
}

/* Donut -------------------------------------------------------------- */

export function Donut({ data, center }: { data: { label: string; value: number; color: string; detail?: string }[]; center: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-5">
      <div className="relative size-[180px]">
        <ResponsiveContainer>
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="label" innerRadius={62} outerRadius={86} startAngle={90} endAngle={-270} stroke="var(--surface)" strokeWidth={3} isAnimationActive={false}>
              {data.map((d) => (
                <Cell key={d.label} fill={d.color} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center text-center">{center}</div>
      </div>
      <ul className="w-full space-y-3">
        {data.map((d) => (
          <li key={d.label} className="flex items-start gap-3">
            <span className="mt-1 size-2.5 shrink-0 rounded-sm" style={{ background: d.color }} aria-hidden />
            <span className="flex-1">
              <span className="flex justify-between text-sm font-medium text-fg">
                {d.label}
                <span className="num">{d.value}%</span>
              </span>
              {d.detail && <span className="text-xs text-fg-2">{d.detail}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

/* Forest plot -------------------------------------------------------- */

export function ForestPlot({ data, selected, onSelect }: { data: Feature[]; selected: string; onSelect: (id: string) => void }) {
  const min = -3
  const max = 11
  const pos = (v: number) => ((v - min) / (max - min)) * 100
  const ticks = [-2, 0, 2, 4, 6, 8, 10]
  return (
    <div>
      <div className="grid grid-cols-[200px_1fr_150px] gap-3 px-2 pb-2 text-xs text-fg-2">
        <span>Feature</span>
        <span className="relative h-4">
          {ticks.map((t) => (
            <span key={t} className="num absolute -translate-x-1/2" style={{ left: `${pos(t)}%` }}>
              {t > 0 ? `+${t}` : t}
            </span>
          ))}
        </span>
        <span className="text-right">Effect (range)</span>
      </div>
      <ul className="relative" role="listbox" aria-label="Features by effect on 90-day retention">
        {data.map((f) => {
          const isSel = f.id === selected
          return (
            <li key={f.id} role="option" aria-selected={isSel}>
              <button
                type="button"
                onClick={() => onSelect(f.id)}
                className={cx('grid w-full grid-cols-[200px_1fr_150px] items-center gap-3 rounded-md px-2 py-2.5 text-left', isSel ? 'bg-raised' : 'hover:bg-raised/50')}
                aria-label={`${f.name}: ${fmtPts(f.lift)}, range ${fmtRange(f.lo, f.hi)}${f.significant ? '' : ', not significant'}`}
              >
                <span className="flex min-w-0 flex-col">
                  <span className={cx('truncate text-sm font-medium', f.significant ? 'text-fg' : 'text-fg-2')}>{f.name}</span>
                  {!f.significant && <span className="mt-0.5 w-fit rounded border border-line px-1.5 text-[11px] leading-4 text-fg-2">Not significant</span>}
                </span>
                <span className="relative block h-6">
                  <span className="absolute top-0 bottom-0 w-px bg-line-strong" style={{ left: `${pos(0)}%` }} aria-hidden />
                  <span
                    className="absolute top-1/2 h-[3px] -translate-y-1/2 rounded-full"
                    style={{ left: `${pos(f.lo)}%`, width: `${pos(f.hi) - pos(f.lo)}%`, background: f.significant ? 'var(--accent)' : 'var(--border-strong)' }}
                    aria-hidden
                  />
                  <span
                    className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2"
                    style={{
                      left: `${pos(f.lift)}%`,
                      background: f.significant ? 'var(--accent)' : 'var(--surface)',
                      borderColor: f.significant ? 'var(--accent)' : 'var(--text-2)',
                    }}
                    aria-hidden
                  />
                </span>
                <span className="num text-right text-sm">
                  <span className={cx('font-semibold', f.significant ? 'text-fg' : 'text-fg-2')}>{fmtPts(f.lift)}</span>
                  <span className="block text-xs text-fg-2">{fmtRange(f.lo, f.hi)}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
      <div className="mt-3 grid grid-cols-[200px_1fr_150px] gap-3 px-2 text-xs text-fg-2">
        <span />
        <span className="relative h-4">
          <span className="absolute -translate-x-1/2 whitespace-nowrap" style={{ left: `${pos(0)}%` }}>
            No effect
          </span>
          <span className="absolute right-0 whitespace-nowrap">Keeps more accounts →</span>
        </span>
        <span />
      </div>
    </div>
  )
}

/* Naive vs causal ---------------------------------------------------- */

export function NaiveVsCausalBars({ data = allFeatures }: { data?: Feature[] }) {
  const max = 12
  return (
    <div>
      <div className="mb-4 flex items-center gap-5 text-xs text-fg-2">
        <span className="flex items-center gap-2">
          <span className="h-2.5 w-5 rounded-sm bg-line-strong" aria-hidden />
          Simple comparison (users vs non-users)
        </span>
        <span className="flex items-center gap-2">
          <span className="h-2.5 w-5 rounded-sm bg-accent" aria-hidden />
          Real effect (after adjusting for who uses it)
        </span>
      </div>
      <div className="grid grid-cols-7 gap-4">
        {data.map((f) => (
          <div key={f.id} className="flex flex-col">
            <div className="flex h-[180px] items-end justify-center gap-2 border-b border-line">
              {[
                { v: f.naive, bg: 'var(--border-strong)', label: 'Simple' },
                { v: f.lift, bg: f.significant ? 'var(--accent)' : 'var(--text-2)', label: 'Real' },
              ].map((b) => (
                <div key={b.label} className="flex w-7 flex-col items-center justify-end" style={{ height: '100%' }}>
                  <span className="num mb-1 text-xs font-semibold text-fg">+{b.v}</span>
                  <span className="w-full rounded-t-sm" style={{ height: `${(Math.max(b.v, 0.2) / max) * 150}px`, background: b.bg }} aria-hidden />
                </div>
              ))}
            </div>
            <p className={cx('mt-2 text-center text-xs leading-4', f.id === 'saved-dashboards' ? 'font-semibold text-fg' : 'text-fg-2')}>{f.name}</p>
          </div>
        ))}
      </div>
      <SrTable caption="Simple comparison versus real effect, in points of 90-day retention" head={['Feature', 'Simple', 'Real']} rows={data.map((f) => [f.name, f.naive, f.lift])} />
    </div>
  )
}

/* Variant bars ------------------------------------------------------- */

export function VariantBars({ variants, color }: { variants: { name: string; value: number; accounts: number }[]; color: string }) {
  const min = 50
  const max = 70
  return (
    <ul className="space-y-3">
      {variants.map((v, i) => (
        <li key={v.name} className="grid grid-cols-[120px_1fr_56px] items-center gap-3">
          <span className="text-xs text-fg">
            {v.name}
            <span className="num block text-fg-2">{fmtInt(v.accounts)} accts</span>
          </span>
          <span className="h-5 rounded-sm bg-raised">
            <span className="block h-full rounded-sm" style={{ width: `${((v.value - min) / (max - min)) * 100}%`, background: i === 0 ? 'var(--border-strong)' : color }} />
          </span>
          <span className="num text-right text-sm font-semibold text-fg">{v.value.toFixed(1)}%</span>
        </li>
      ))}
      <li className="pl-[132px] text-xs text-fg-2">Axis starts at {min}% to show the difference</li>
    </ul>
  )
}

/* Outcome chart ------------------------------------------------------ */

export function OutcomeChart({ data, color }: { data: { week: string; target: number; control: number }[]; color: string }) {
  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 20, right: 96, bottom: 4, left: -12 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="2 4" />
          <XAxis dataKey="week" tick={axisTick} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
          <YAxis domain={[3, 5.5]} tick={axisTick} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} width={48} />
          <Tooltip {...tooltipProps} formatter={(v, n) => [`${v}% churn`, n === 'target' ? 'Growth Teams (got the tip)' : 'Control group']} />
          <ReferenceLine x="Launch" stroke="var(--border-strong)" strokeDasharray="3 3" label={{ value: 'Tip launched', position: 'top', fill: 'var(--text-2)', fontSize: 11 }} />
          <Line
            type="monotone"
            dataKey="control"
            stroke="var(--text-2)"
            strokeDasharray="5 4"
            strokeWidth={1.75}
            dot={false}
            isAnimationActive={false}
            label={(p: { x?: number | string; y?: number | string; index?: number }) =>
              p.index === data.length - 1 ? (
                <text key="c" x={Number(p.x) + 8} y={Number(p.y) + 4} fontSize={12} fill="var(--text-2)">
                  Control 4.5%
                </text>
              ) : (
                <g key={`c${p.index}`} />
              )
            }
          />
          <Line
            type="monotone"
            dataKey="target"
            stroke={color}
            strokeWidth={2.5}
            dot={{ r: 2.5, fill: color }}
            isAnimationActive={false}
            label={(p: { x?: number | string; y?: number | string; index?: number }) =>
              p.index === data.length - 1 ? (
                <text key="t" x={Number(p.x) + 8} y={Number(p.y) + 4} fontSize={12} fontWeight={600} fill={color}>
                  With tip 3.7%
                </text>
              ) : (
                <g key={`t${p.index}`} />
              )
            }
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

/* Account survival --------------------------------------------------- */

export function AccountSurvival({ data, color, segmentName }: { data: { day: number; account: number; segment: number }[]; color: string; segmentName: string }) {
  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 12, right: 16, bottom: 4, left: -12 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeDasharray="2 4" />
          <XAxis dataKey="day" type="number" domain={[0, 120]} ticks={[0, 30, 60, 90, 120]} tick={axisTick} tickLine={false} axisLine={{ stroke: 'var(--border)' }} tickFormatter={(v) => `${v}d`} />
          <YAxis domain={[0, 100]} tick={axisTick} tickLine={false} axisLine={false} tickFormatter={(v) => `${v}%`} width={48} />
          <Tooltip {...tooltipProps} labelFormatter={(d) => `Day ${d}`} formatter={(v, n) => [`${v}% chance still subscribed`, n === 'account' ? 'This account' : `${segmentName} average`]} />
          <ReferenceLine y={50} stroke="var(--border-strong)" strokeDasharray="3 3" label={{ value: '50%', position: 'insideTopRight', fill: 'var(--text-2)', fontSize: 11 }} />
          <Line type="monotone" dataKey="segment" stroke={color} strokeDasharray="5 4" strokeWidth={1.5} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="account" stroke="var(--risk-high)" strokeWidth={2.5} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
