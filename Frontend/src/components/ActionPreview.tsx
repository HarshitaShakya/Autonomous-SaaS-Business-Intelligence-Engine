import { CalendarClock, Mail, MousePointerClick, Split, Tag } from 'lucide-react'
import type { ReactNode } from 'react'
import type { ActionPreviewData } from '@/data/mock'
import { fmtInt } from '@/lib/format'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[120px_1fr] gap-3 py-1.5 text-xs">
      <dt className="text-fg-2">{label}</dt>
      <dd className="text-fg">{children}</dd>
    </div>
  )
}

export default function ActionPreview({ data, accounts, sendTime }: { data: ActionPreviewData; accounts?: number; sendTime?: string }) {
  if (data.kind === 'email') {
    return (
      <div className="overflow-hidden rounded-md border border-line">
        <div className="flex items-center gap-2 border-b border-line bg-raised px-4 py-2 text-xs font-semibold text-fg-2">
          <Mail size={14} aria-hidden /> Email preview
        </div>
        <div className="space-y-2 bg-canvas/40 px-4 py-3">
          <p className="text-sm font-semibold text-fg">{data.subject}</p>
          <p className="text-xs leading-5 text-fg-2">{data.body}</p>
        </div>
        <dl className="border-t border-line px-4 py-2">
          <Row label="Audience">{accounts ? data.audience.replace(/^[\d,]+/, fmtInt(accounts)) : data.audience}</Row>
          <Row label="Send time">
            <span className="inline-flex items-center gap-1">
              <CalendarClock size={12} aria-hidden /> {sendTime ?? data.sendTime}
            </span>
          </Row>
        </dl>
      </div>
    )
  }
  if (data.kind === 'abTest') {
    return (
      <div className="overflow-hidden rounded-md border border-line">
        <div className="flex items-center gap-2 border-b border-line bg-raised px-4 py-2 text-xs font-semibold text-fg-2">
          <Split size={14} aria-hidden /> A/B test setup
        </div>
        <div className="grid grid-cols-2 gap-3 px-4 py-3">
          {data.variants.map((v) => (
            <div key={v.name} className="rounded-md border border-line bg-canvas/40 p-3">
              <p className="text-xs font-semibold text-fg">{v.name}</p>
              <p className="mt-1 text-xs text-fg-2">{v.description}</p>
            </div>
          ))}
        </div>
        <dl className="border-t border-line px-4 py-2">
          <Row label="Split">{data.split}</Row>
          <Row label="Duration">{data.duration}</Row>
          <Row label="Success metric">{data.metric}</Row>
          {accounts !== undefined && <Row label="Accounts">{fmtInt(accounts)}</Row>}
        </dl>
      </div>
    )
  }
  if (data.kind === 'pricing') {
    return (
      <div className="overflow-hidden rounded-md border border-line">
        <div className="flex items-center gap-2 border-b border-line bg-raised px-4 py-2 text-xs font-semibold text-fg-2">
          <Tag size={14} aria-hidden /> Pricing change
        </div>
        <div className="flex items-center gap-4 px-4 py-3">
          <div>
            <p className="text-xs text-fg-2">Current</p>
            <p className="num text-sm text-fg-2 line-through">{data.oldPrice}</p>
          </div>
          <span className="text-fg-2" aria-hidden>
            →
          </span>
          <div>
            <p className="text-xs text-fg-2">Offer</p>
            <p className="num text-sm font-semibold text-fg">{data.newPrice}</p>
          </div>
        </div>
        <dl className="border-t border-line px-4 py-2">
          <Row label="Plan">{data.plan}</Row>
          <Row label="Accounts">{fmtInt(accounts ?? data.accounts)}</Row>
          <Row label="When shown">{data.billing}</Row>
          <Row label="Effective">{data.effectiveDate}</Row>
        </dl>
      </div>
    )
  }
  return (
    <div className="overflow-hidden rounded-md border border-line">
      <div className="flex items-center gap-2 border-b border-line bg-raised px-4 py-2 text-xs font-semibold text-fg-2">
        <MousePointerClick size={14} aria-hidden /> In-app guide · shown on <span className="font-mono text-fg">{data.targetPage}</span>
      </div>
      <ol className="space-y-2 px-4 py-3">
        {data.steps.map((s, i) => (
          <li key={s} className="flex items-start gap-3 text-xs text-fg">
            <span className="num inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-raised text-[11px] font-semibold text-fg-2">{i + 1}</span>
            <span className="pt-0.5">{s}</span>
          </li>
        ))}
      </ol>
      <dl className="border-t border-line px-4 py-2">
        <Row label="Shown when">{data.trigger}</Row>
        {accounts !== undefined && <Row label="Accounts">{fmtInt(accounts)}</Row>}
      </dl>
    </div>
  )
}
