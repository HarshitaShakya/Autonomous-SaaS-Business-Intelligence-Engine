import { useEffect, useId, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { AlertTriangle, ArrowRight, Check, ChevronDown, Pencil, X } from 'lucide-react'
import type { Recommendation } from '@/data/mock'
import { fmtInt, fmtMoney, fmtPts, fmtRange } from '@/lib/format'
import { useApp } from '@/state/AppState'
import ActionPreview from './ActionPreview'
import { Modal } from './Overlay'
import { ActionTypeTag, Button, Card, ConfidenceBadge, HowCalculated, SegmentChip, StatusPill, cx } from './ui'

const rejectPresets = ['Not now', 'Disagree with the evidence', 'Overlaps another action', 'Other']

function Metric({ label, value, sub, how }: { label: string; value: string; sub?: string; how: string }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1 text-xs text-fg-2">
        {label}
        <HowCalculated label={label}>{how}</HowCalculated>
      </div>
      <p className="num mt-0.5 text-lg font-semibold text-fg">{value}</p>
      {sub && <p className="num text-xs text-fg-2">{sub}</p>}
    </div>
  )
}

export default function RecommendationCard({ rec, expanded = false, compact = false }: { rec: Recommendation; expanded?: boolean; compact?: boolean }) {
  const { state, approve, reject, edit, toast } = useApp()
  const navigate = useNavigate()
  const rs = state.recs[rec.id]
  const accounts = rs?.edited?.accounts ?? rec.accounts
  const sendTime = rs?.edited?.sendTime ?? rec.sendTime
  const [open, setOpen] = useState(expanded)
  const [modal, setModal] = useState<'approve' | 'reject' | 'edit' | null>(null)
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const [editAccounts, setEditAccounts] = useState(accounts)
  const [editTime, setEditTime] = useState(sendTime ?? '')
  const evidenceId = useId()
  const live = state.mode === 'live'

  useEffect(() => setOpen(expanded), [expanded])

  const mrr = Math.round((rec.mrrRetained * accounts) / rec.accounts)

  const doApprove = () => {
    approve(rec.id)
    setModal(null)
    toast({
      tone: 'success',
      title: live ? 'Approved — queued for live execution' : 'Approved — queued as Dry-run',
      body: `${rec.title} · ${fmtInt(accounts)} accounts`,
      action: { label: 'View in log', to: '/actions' },
    })
  }

  const doReject = () => {
    const r = reason === 'Other' ? note.trim() || 'Other' : note.trim() ? `${reason}: ${note.trim()}` : reason
    reject(rec.id, r)
    setModal(null)
    toast({ tone: 'info', title: 'Recommendation rejected', body: `${rec.title}. The Strategy agent will use your reason next run.`, action: { label: 'View rejected', to: '/recommendations?tab=rejected' } })
  }

  const doEdit = () => {
    const n = Math.max(1, Math.min(rec.accounts, Math.round(editAccounts) || rec.accounts))
    edit(rec.id, n, rec.sendTime ? editTime : undefined)
    setModal(null)
    toast({ tone: 'success', title: 'Changes saved', body: `Audience set to ${fmtInt(n)} accounts.` })
  }

  const chips = (
    <div className="flex flex-wrap items-center gap-2">
      <SegmentChip id={rec.segment} />
      <ActionTypeTag type={rec.type} />
      <ConfidenceBadge level={rec.confidence} />
      {rs.status === 'pending' && <StatusPill status="Pending" label="Needs decision" />}
      {rs.status === 'approved' && <StatusPill status="Approved" />}
      {rs.status === 'rejected' && <StatusPill status="Rejected" />}
      {rs.edited && <StatusPill status="Edited" />}
    </div>
  )

  if (compact) {
    return (
      <Card as="article" className="flex items-center gap-5 p-4.5 hover:border-accent/40 bg-surface/90 hover:shadow-md transition-all duration-150">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-xs text-fg-2">
            <span className="font-mono text-accent font-semibold">{rec.id}</span>
            <span aria-hidden className="text-fg-2/40">·</span>
            <SegmentChip id={rec.segment} />
            <ActionTypeTag type={rec.type} />
            {rec.confidence === 'Low' && <ConfidenceBadge level="Low" />}
          </div>
          <h3 className="mt-2 truncate text-sm font-bold text-fg tracking-tight">{rec.title}</h3>
          <p className="num mt-1 text-xs text-fg-2">
            {fmtInt(accounts)} accounts · effect <span className="font-medium text-emerald-400">{fmtPts(rec.lift)}</span> ({fmtRange(rec.lo, rec.hi)})
          </p>
        </div>
        <div className="text-right">
          <p className="text-[11px] font-semibold text-fg-2 uppercase tracking-wider">Est. MRR Retained</p>
          <p className="num text-xl font-bold text-emerald-400 tracking-tight">{fmtMoney(mrr)}</p>
        </div>
        <Button variant="decision" size="sm" onClick={() => navigate(`/recommendations?tab=pending&expand=${rec.id}`)}>
          Review <ArrowRight size={14} aria-hidden />
        </Button>
      </Card>
    )
  }

  return (
    <Card as="article" aria-label={rec.title} className={cx('relative overflow-hidden', rs.status === 'pending' && 'border-line')}>
      {rec.lowConfidence && rs.status === 'pending' && <span className="absolute top-0 bottom-0 left-0 w-1 bg-risk-med" aria-hidden />}
      <div className="p-5">
        <div className="flex items-start justify-between gap-4">
          {chips}
          <span className="font-mono text-xs text-fg-2">{rec.id}</span>
        </div>
        <h3 className="mt-3 text-base font-semibold text-fg">{rec.title}</h3>
        <p className="mt-1.5 max-w-3xl text-sm leading-6 text-fg-2">{rec.narrative}</p>

        {rec.lowConfidence && rs.status === 'pending' && (
          <p className="mt-3 flex items-start gap-2 rounded-md border border-risk-med/35 bg-risk-med/8 px-3 py-2 text-xs text-fg">
            <AlertTriangle size={14} className="mt-0.5 shrink-0 text-risk-med" aria-hidden />
            {rec.lowConfidence}
          </p>
        )}

        <div className="mt-4 grid grid-cols-3 gap-6 rounded-md border border-line bg-canvas/40 px-4 py-3">
          <Metric
            label="Accounts targeted"
            value={fmtInt(accounts)}
            sub={rs.edited ? `of ${fmtInt(rec.accounts)} suggested` : undefined}
            how="At-risk accounts in this segment that match the trigger rule and have not received a similar action in the last 30 days."
          />
          <Metric
            label="Est. MRR retained (90d)"
            value={fmtMoney(mrr)}
            how="Accounts targeted × chance each would otherwise cancel × the measured effect, multiplied by their monthly revenue."
          />
          <Metric
            label="Effect on retention"
            value={fmtPts(rec.lift)}
            sub={`Likely range ${fmtRange(rec.lo, rec.hi)}`}
            how="How many more accounts out of 100 keep their subscription for 90 days because of this change, measured against similar accounts. The range shows where the true number most likely sits."
          />
        </div>

        {rs.status === 'pending' && (
          <div className="mt-4 flex items-center gap-2">
            <Button variant="primary" icon={<Check size={16} aria-hidden />} onClick={() => setModal('approve')}>
              Approve
            </Button>
            <Button variant="secondary" icon={<X size={16} aria-hidden />} onClick={() => setModal('reject')}>
              Reject
            </Button>
            <Button
              variant="ghost"
              icon={<Pencil size={14} aria-hidden />}
              onClick={() => {
                setEditAccounts(accounts)
                setEditTime(sendTime ?? '')
                setModal('edit')
              }}
            >
              Edit
            </Button>
            <span className="ml-auto text-xs text-fg-2">{live ? 'Live mode: approving will reach real customers' : 'Dry-run mode: nothing is sent until you switch to Live'}</span>
          </div>
        )}
        {rs.status === 'approved' && (
          <div className="mt-4 flex items-center gap-3 rounded-md border border-accent/25 bg-accent/8 px-3 py-2 text-xs text-fg">
            <Check size={14} className="text-accent" aria-hidden />
            Approved by {rs.decidedBy} {rs.decidedAt} · {live ? 'Queued for execution' : 'Queued as Dry-run'}
            <Link to="/actions" className="ml-auto font-semibold text-accent hover:underline">
              View in log
            </Link>
          </div>
        )}
        {rs.status === 'rejected' && (
          <div className="mt-4 flex items-center gap-3 rounded-md border border-line bg-raised px-3 py-2 text-xs text-fg">
            <X size={14} className="text-fg-2" aria-hidden />
            Rejected by {rs.decidedBy} {rs.decidedAt} · Reason: <span className="font-medium">{rs.rejectReason}</span>
          </div>
        )}
      </div>

      <div className="border-t border-line">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={evidenceId}
          onClick={() => setOpen((o) => !o)}
          className="flex w-full items-center justify-between px-5 py-3 text-left text-sm font-medium text-fg-2 hover:text-fg"
        >
          {open ? 'Hide evidence and preview' : 'View evidence and preview'}
          <ChevronDown size={16} className={cx('transition-transform', open && 'rotate-180')} aria-hidden />
        </button>
        {open && (
          <div id={evidenceId} className="grid grid-cols-2 gap-5 px-5 pb-5">
            <div>
              <p className="mb-2 text-xs font-semibold tracking-wide text-fg-2 uppercase">Evidence</p>
              <table className="w-full text-xs">
                <caption className="sr-only">Evidence for {rec.title}</caption>
                <tbody>
                  {rec.evidence.map((e) => (
                    <tr key={e.label} className="border-b border-line last:border-0">
                      <th scope="row" className="py-2 pr-3 text-left font-normal text-fg-2">
                        {e.label}
                      </th>
                      <td className="num py-2 text-right font-medium text-fg">{e.value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {rec.featureId && (
                <Link to={`/feature-impact?feature=${rec.featureId}`} className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-accent hover:underline">
                  See feature analysis <ArrowRight size={12} aria-hidden />
                </Link>
              )}
            </div>
            <div>
              <p className="mb-2 text-xs font-semibold tracking-wide text-fg-2 uppercase">What will happen</p>
              <ActionPreview data={rec.preview} accounts={accounts} sendTime={sendTime} />
            </div>
          </div>
        )}
      </div>

      <Modal
        open={modal === 'approve'}
        onClose={() => setModal(null)}
        tone={live ? 'warning' : undefined}
        title={`Approve and queue "${rec.verb}"?`}
        description={
          <span className="num">
            {fmtInt(accounts)} accounts · Mode: {live ? 'Live' : 'Dry-run, no real messages sent'}
          </span>
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(null)}>
              Cancel
            </Button>
            <Button variant="primary" data-autofocus onClick={doApprove} icon={<Check size={16} aria-hidden />}>
              {live ? 'Approve and run live' : 'Approve and queue'}
            </Button>
          </>
        }
      >
        {live ? (
          <p className="flex items-start gap-2 rounded-md border border-risk-med/40 bg-risk-med/10 px-3 py-2 text-sm text-fg">
            <AlertTriangle size={16} className="mt-0.5 shrink-0 text-risk-med" aria-hidden />
            You are in Live mode. This will {rec.type === 'Pricing change' ? 'change real prices' : rec.type === 'Targeted email' ? 'send real emails' : 'show real changes'} to {fmtInt(accounts)} customers.
          </p>
        ) : (
          <p className="text-sm text-fg-2">
            The Action agent will prepare this as a dry run so you can check exactly what would go out. Switch to Live in the top bar when you are ready.
          </p>
        )}
        {rec.lowConfidence && <p className="mt-3 text-xs text-risk-med">{rec.lowConfidence}</p>}
      </Modal>

      <Modal
        open={modal === 'reject'}
        onClose={() => setModal(null)}
        title="Reject this recommendation?"
        description={rec.title}
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(null)}>
              Cancel
            </Button>
            <Button variant="danger" disabled={!reason || (reason === 'Other' && !note.trim())} onClick={doReject}>
              Reject recommendation
            </Button>
          </>
        }
      >
        <fieldset>
          <legend className="mb-2 text-sm font-medium text-fg">Why are you rejecting it? (required)</legend>
          <div className="space-y-1.5">
            {rejectPresets.map((p) => (
              <label key={p} className={cx('flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-sm', reason === p ? 'border-accent/60 bg-accent/8 text-fg' : 'border-line text-fg-2 hover:text-fg')}>
                <input type="radio" name={`reason-${rec.id}`} value={p} checked={reason === p} onChange={() => setReason(p)} className="accent-[var(--accent)]" />
                {p}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="mt-4 block text-xs text-fg-2">
          {reason === 'Other' ? 'Tell us more (required)' : 'Add a note (optional)'}
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            className="mt-1 block w-full resize-none rounded-md border border-line bg-canvas px-3 py-2 text-sm text-fg placeholder:text-muted"
            placeholder="This helps the Strategy agent improve future recommendations."
          />
        </label>
      </Modal>

      <Modal
        open={modal === 'edit'}
        onClose={() => setModal(null)}
        title="Edit before approving"
        description={rec.title}
        footer={
          <>
            <Button variant="ghost" onClick={() => setModal(null)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={doEdit}>
              Save changes
            </Button>
          </>
        }
      >
        <label className="block text-sm font-medium text-fg">
          Audience size
          <span className="mt-0.5 block text-xs font-normal text-fg-2">Start smaller to limit risk. Highest-risk accounts are kept first. Max {fmtInt(rec.accounts)}.</span>
          <input
            type="number"
            min={1}
            max={rec.accounts}
            value={editAccounts}
            onChange={(e) => setEditAccounts(Number(e.target.value))}
            className="num mt-2 h-9 w-40 rounded-md border border-line bg-canvas px-3 text-sm text-fg"
          />
        </label>
        {rec.sendTime && (
          <label className="mt-4 block text-sm font-medium text-fg">
            Send time
            <select value={editTime} onChange={(e) => setEditTime(e.target.value)} className="mt-2 block h-9 w-64 rounded-md border border-line bg-canvas px-3 text-sm text-fg">
              {[rec.sendTime, 'Mon 09:00 local time', 'Tue 10:00 local time', 'Wed 09:00 local time', 'Thu 14:00 local time']
                .filter((v, i, a) => a.indexOf(v) === i)
                .map((t) => (
                  <option key={t}>{t}</option>
                ))}
            </select>
          </label>
        )}
      </Modal>
    </Card>
  )
}
