import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { ArrowDownRight, ArrowRight, ArrowUpRight, Sparkles } from 'lucide-react'
import { Sparkline } from './charts'
import { Card, HowCalculated, Skeleton, cx } from './ui'

export default function KpiCard({
  label,
  value,
  sub,
  delta,
  good,
  series,
  how,
  tone,
  to,
  loading,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  delta?: string
  good?: boolean
  series?: number[]
  how: ReactNode
  tone?: 'decision'
  to?: string
  loading?: boolean
}) {
  const up = delta?.startsWith('+')
  const isDecision = tone === 'decision'

  return (
    <Card
      as="div"
      className={cx(
        'group relative col-span-2 flex flex-col p-4.5 rounded-card transition-all duration-200',
        isDecision
          ? 'border-amber-500/40 bg-gradient-to-b from-amber-500/[0.08] to-surface shadow-md shadow-amber-500/5 hover:border-amber-500/60'
          : 'hover:border-line-strong'
      )}
    >
      {/* Subtle top ambient highlight */}
      <div
        className={cx(
          'absolute top-0 left-0 right-0 h-[2px] transition-opacity duration-300',
          isDecision
            ? 'bg-gradient-to-r from-amber-500/40 via-amber-400 to-amber-500/40 opacity-100'
            : 'bg-gradient-to-r from-transparent via-white/10 to-transparent opacity-40 group-hover:via-accent/60 group-hover:opacity-100'
        )}
      />

      <div className="flex items-center justify-between gap-1">
        <div className="flex items-center gap-1.5">
          <p className={cx('text-xs font-semibold tracking-wide uppercase', isDecision ? 'text-amber-400' : 'text-fg-2')}>
            {label}
          </p>
          <HowCalculated label={label}>{how}</HowCalculated>
        </div>
        {isDecision && (
          <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/20 px-1.5 py-0.5 text-[10px] font-bold text-amber-300">
            <span className="size-1.5 rounded-full bg-amber-400 pulse-amber" />
            ACTION
          </span>
        )}
      </div>

      {loading ? (
        <>
          <Skeleton className="mt-3.5 h-8 w-24" />
          <Skeleton className="mt-3 h-4 w-32" />
        </>
      ) : (
        <>
          <div className="mt-3 flex items-end justify-between gap-2">
            <p className={cx('num text-2xl font-bold tracking-tight', isDecision ? 'text-amber-300' : 'text-fg')}>
              {value}
            </p>
            {series && (
              <div className="pb-0.5 opacity-90 transition-opacity group-hover:opacity-100">
                <Sparkline
                  data={series}
                  width={76}
                  height={28}
                  color={good === undefined ? 'var(--text-2)' : good ? 'var(--risk-low)' : 'var(--risk-high)'}
                  label={`${label} trend over 12 weeks`}
                />
              </div>
            )}
          </div>

          <div className="mt-auto pt-3 text-xs text-fg-2">
            {delta ? (
              <span className="inline-flex items-center gap-1.5">
                <span
                  className={cx(
                    'num inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[11px] font-semibold border',
                    good
                      ? 'bg-risk-low/10 text-risk-low border-risk-low/20'
                      : 'bg-risk-high/10 text-risk-high border-risk-high/20'
                  )}
                >
                  {up ? <ArrowUpRight size={12} strokeWidth={2.5} aria-hidden /> : <ArrowDownRight size={12} strokeWidth={2.5} aria-hidden />}
                  {delta}
                </span>
                <span className="text-[11px] text-fg-2/80">vs last 30d</span>
              </span>
            ) : (
              sub
            )}
          </div>

          {to && (
            <Link
              to={to}
              className="mt-2.5 inline-flex items-center gap-1 text-xs font-semibold text-amber-400 hover:text-amber-300 hover:underline transition-colors"
            >
              Review now <ArrowRight size={12} aria-hidden />
            </Link>
          )}
        </>
      )}
    </Card>
  )
}
