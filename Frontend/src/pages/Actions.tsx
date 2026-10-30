import { useState } from 'react'
import { FileJson, PauseCircle, PlayCircle, RotateCw } from 'lucide-react'
import { actionStats, experiment, outcome, segmentById, type ActionLogRow, type SegmentId } from '@/data/mock'
import { fmtInt } from '@/lib/format'
import { useApp } from '@/state/AppState'
import DataTable from '@/components/DataTable'
import { Modal } from '@/components/Overlay'
import { OutcomeChart, VariantBars } from '@/components/charts'
import { ActionTypeTag, Button, Card, CardHeader, PageHeader, SegmentChip, StatTile, StatusPill, Switch, cx } from '@/components/ui'

export default function Actions() {
  const { state, retry, setAutomation, toast } = useApp()
  const [payload, setPayload] = useState<ActionLogRow | null>(null)
  const [confirmPause, setConfirmPause] = useState(false)
  const loading = state.lastRun.loading
  const paused = state.automation === 'paused'
  const rows = state.segmentFilter === 'all' ? state.log : state.log.filter((r) => r.segment === state.segmentFilter)

  return (
    <>
      <PageHeader title="Actions & Impact" description="Everything the Action agent has run, and whether it worked." agent="Action agent" agentStatus={paused ? 'Paused' : 'Active'} />

      {actionStats.map((s) => (
        <StatTile key={s.label} label={s.label} value={s.value} how={s.hint} loading={loading} />
      ))}

      <Card className="col-span-12 flex items-center gap-5 px-5 py-4">
        <span className={cx('inline-flex size-9 items-center justify-center rounded-full', paused ? 'bg-risk-med/12 text-risk-med' : 'bg-risk-low/12 text-risk-low')} aria-hidden>
          {paused ? <PauseCircle size={18} /> : <PlayCircle size={18} />}
        </span>
        <div className="flex-1">
          <p className="text-sm font-semibold text-fg">Automation is {paused ? 'paused' : 'on'}</p>
          <p className="text-xs text-fg-2">
            {paused ? 'Approved actions wait in the queue until you turn automation back on.' : 'Approved actions run automatically. Every action still needs a human approval first.'}
          </p>
        </div>
        <span className="flex items-center gap-2 text-xs text-fg-2">
          Run approved actions automatically
          <Switch
            checked={!paused}
            label="Run approved actions automatically"
            onChange={(v) => {
              setAutomation(v ? 'on' : 'paused')
              toast({ tone: 'info', title: v ? 'Automation turned on' : 'Automation paused' })
            }}
          />
        </span>
        <Button variant="danger" size="sm" disabled={paused} onClick={() => setConfirmPause(true)} icon={<PauseCircle size={14} aria-hidden />}>
          Pause all automation
        </Button>
      </Card>

      <Card className="col-span-12">
        <CardHeader title="Execution log" subtitle="Newest first. Dry runs show exactly what would have been sent." />
        <DataTable<ActionLogRow>
          caption="Execution log"
          loading={loading}
          rows={rows}
          rowKey={(r) => r.id}
          columns={[
            { key: 'time', header: 'Time', width: '120px', render: (r) => <span className="text-fg-2">{r.time}</span> },
            {
              key: 'rec',
              header: 'Recommendation',
              render: (r) => (
                <span>
                  <span className="block font-medium">{r.recommendation}</span>
                  {r.segment && typeof r.segment === 'string' && r.segment in segmentById ? (
                    <span className="mt-0.5 flex items-center gap-1.5 text-xs text-fg-2">
                      <span className="size-1.5 rounded-full" style={{ background: segmentById[r.segment as SegmentId].color }} aria-hidden />
                      {segmentById[r.segment as SegmentId].name}
                    </span>
                  ) : null}
                </span>
              ),
            },
            { key: 'type', header: 'Type', render: (r) => <ActionTypeTag type={r.type} /> },
            { key: 'by', header: 'Approved by', render: (r) => r.approvedBy },
            {
              key: 'status',
              header: 'Status',
              render: (r) => (
                <span className="flex flex-col items-start gap-1">
                  <StatusPill status={r.status} />
                  {r.status === 'Failed' && <span className="text-xs text-risk-high">{r.error}</span>}
                </span>
              ),
            },
            { key: 'acc', header: 'Accounts', align: 'right', render: (r) => fmtInt(r.accounts) },
            {
              key: 'act',
              header: <span className="sr-only">Actions</span>,
              align: 'right',
              render: (r) => (
                <span className="flex justify-end gap-2">
                  {r.status === 'Failed' && (
                    <Button size="sm" variant="secondary" icon={<RotateCw size={14} aria-hidden />} onClick={() => retry(r.id)}>
                      Retry
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" icon={<FileJson size={14} aria-hidden />} onClick={() => setPayload(r)}>
                    View payload
                  </Button>
                </span>
              ),
            },
          ]}
        />
      </Card>

      <Card className="col-span-6">
        <CardHeader
          title={`Experiment: ${experiment.name}`}
          subtitle={
            <span className="flex items-center gap-2">
              <SegmentChip id={experiment.segment} /> Day {experiment.day} of {experiment.duration}
            </span>
          }
          right={<StatusPill status="Running" />}
          how="Accounts were split 50/50 at random. We compare the share of accounts still active after 30 days. The p-value is the chance of seeing a gap this big if v2 made no difference."
        />
        <div className="px-5 pb-5">
          <div className="mb-5 h-1.5 rounded-full bg-raised" role="progressbar" aria-valuemin={0} aria-valuemax={experiment.duration} aria-valuenow={experiment.day} aria-label="Experiment progress">
            <span className="block h-full rounded-full bg-accent" style={{ width: `${(experiment.day / experiment.duration) * 100}%` }} />
          </div>
          <p className="mb-3 text-xs text-fg-2">{experiment.metric}</p>
          <VariantBars variants={experiment.variants} color={segmentById[experiment.segment].color} />
          <div className="mt-5 flex items-center gap-3 rounded-md border border-risk-low/30 bg-risk-low/8 px-3 py-2.5">
            <span className="num text-lg font-semibold text-risk-low">+{experiment.diff} pts</span>
            <span className="text-sm text-fg">vs control · {experiment.verdict}</span>
            <span className="num ml-auto text-xs text-fg-2">p = {experiment.p}</span>
          </div>
          <p className="mt-2 text-xs text-fg-2">Early read. We'll call it at day 21; the gap could still shrink.</p>
        </div>
      </Card>

      <Card className="col-span-6">
        <CardHeader
          title={`Outcome: ${outcome.name}`}
          subtitle={
            <span className="flex items-center gap-2">
              <SegmentChip id={outcome.segment} /> Weekly churn before and after launch
            </span>
          }
          right={<StatusPill status="Executed" label={outcome.verdict} />}
          how="Weekly churn for Growth Teams accounts that saw the tip, next to a matched control group that didn't."
        />
        <div className="px-5 pb-5">
          <OutcomeChart data={outcome.series} color={segmentById[outcome.segment].color} />
          <p className="mt-3 text-sm text-fg">
            Churn fell from <span className="num font-semibold">{outcome.before}%</span> to <span className="num font-semibold">{outcome.after}%</span> while the control group stayed at{' '}
            <span className="num font-semibold">{outcome.control}%</span>.
          </p>
        </div>
      </Card>

      <Modal
        open={!!payload}
        onClose={() => setPayload(null)}
        width={600}
        title="Action payload"
        description={payload && `${payload.recommendation} · ${payload.status}`}
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                navigator.clipboard?.writeText(JSON.stringify(payload?.payload, null, 2)).catch(() => {})
                toast({ tone: 'success', title: 'Payload copied' })
              }}
            >
              Copy JSON
            </Button>
            <Button variant="primary" onClick={() => setPayload(null)}>
              Done
            </Button>
          </>
        }
      >
        <pre className="max-h-[360px] overflow-auto rounded-md border border-line bg-canvas p-4 font-mono text-xs leading-5 text-fg">{JSON.stringify(payload?.payload, null, 2)}</pre>
      </Modal>

      <Modal
        open={confirmPause}
        onClose={() => setConfirmPause(false)}
        tone="warning"
        title="Pause all automation?"
        description="Queued and scheduled actions stop immediately. Running experiments keep collecting data."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmPause(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                setAutomation('paused')
                setConfirmPause(false)
                toast({ tone: 'info', title: 'All automation paused', body: 'Turn it back on from Actions & Impact.' })
              }}
            >
              Pause everything
            </Button>
          </>
        }
      />
    </>
  )
}
