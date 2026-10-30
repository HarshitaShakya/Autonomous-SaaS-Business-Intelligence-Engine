import { useState } from 'react'
import { CheckCircle2, CircleDashed, Loader2, Play, XCircle } from 'lucide-react'
import { agents, canonicalFields, dataQuality, dataSources, runHistory, schemaMappings } from '@/data/mock'
import { useApp } from '@/state/AppState'
import DataTable from '@/components/DataTable'
import { Button, Card, CardHeader, HowCalculated, PageHeader, Select, StatusPill, Tabs, cx } from '@/components/ui'

export default function Pipeline() {
  const { state, refresh, toast } = useApp()
  const [schedule, setSchedule] = useState('daily-06')
  const [mappings, setMappings] = useState(schemaMappings)
  const loading = state.lastRun.loading
  const failed = state.demoState === 'failedRun'
  const failIdx = agents.findIndex((a) => a.id === 'causal')

  return (
    <>
      <PageHeader
        title="Pipeline & Data"
        description="Where the data comes from, how clean it is, and how each analysis run went."
        right={
          <div className="flex items-center gap-2">
            <Select
              label="Schedule"
              value={schedule}
              onChange={(v) => {
                setSchedule(v)
                toast({ tone: 'success', title: 'Schedule updated' })
              }}
              options={[
                { value: 'daily-06', label: 'Daily at 06:00' },
                { value: 'twice', label: 'Twice daily (06:00, 18:00)' },
                { value: 'weekly', label: 'Weekly, Mondays 06:00' },
                { value: 'manual', label: 'Manual only' },
              ]}
            />
            <Button variant="primary" size="sm" onClick={refresh} disabled={loading} icon={loading ? <Loader2 size={14} className="animate-spin" aria-hidden /> : <Play size={14} aria-hidden />}>
              {loading ? 'Running…' : 'Run analysis now'}
            </Button>
          </div>
        }
      />

      <div className="col-span-12">
        <Tabs
          label="Pipeline sections"
          value="data"
          onChange={() => {}}
          tabs={[
            { id: 'data', label: 'Data' },
            { id: 'model', label: 'Model health', disabled: true, hint: 'Coming soon' },
          ]}
        />
      </div>

      <div id="panel-data" role="tabpanel" aria-labelledby="tab-data" className="col-span-12 grid grid-cols-12 gap-6">
        <Card className="col-span-12">
          <CardHeader title="Latest run" subtitle={failed ? 'Yesterday 06:00 · stopped at Feature analysis' : loading ? 'Running now' : `Completed ${state.lastRun.label} · 12m 46s total`} />
          <ol className="grid grid-cols-6 gap-3 px-5 pb-5">
            {agents.map((a, i) => {
              const status: 'ok' | 'failed' | 'skipped' | 'running' = loading ? 'running' : failed ? (i < failIdx ? 'ok' : i === failIdx ? 'failed' : 'skipped') : 'ok'
              return (
                <li key={a.id} className={cx('relative rounded-md border p-3', status === 'failed' ? 'border-risk-high/40 bg-risk-high/8' : 'border-line bg-raised/50')}>
                  <div className="flex items-center gap-2">
                    <span aria-hidden className={cx(status === 'ok' && 'text-risk-low', status === 'failed' && 'text-risk-high', status === 'skipped' && 'text-muted', status === 'running' && 'text-accent')}>
                      {status === 'ok' ? <CheckCircle2 size={16} /> : status === 'failed' ? <XCircle size={16} /> : status === 'running' ? <Loader2 size={16} className="animate-spin" /> : <CircleDashed size={16} />}
                    </span>
                    <span className="num text-xs text-fg-2">Step {i + 1}</span>
                  </div>
                  <p className="mt-2 text-sm font-semibold text-fg">{a.short}</p>
                  <p className="text-xs text-fg-2">{a.name}</p>
                  <p className="num mt-2 text-xs text-fg-2">
                    {status === 'ok' ? a.duration : status === 'failed' ? 'Failed: out of memory' : status === 'running' ? 'Running…' : 'Skipped'}
                  </p>
                </li>
              )
            })}
          </ol>
        </Card>

        <Card className="col-span-12">
          <CardHeader title="Sources" subtitle="Connected systems feeding the agents" />
          <div className="grid grid-cols-5 gap-3 px-5 pb-5">
            {dataSources.map((s) => (
              <div key={s.name} className="rounded-md border border-line bg-raised/50 p-4">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-fg">{s.name}</p>
                  <StatusPill status={s.status} />
                </div>
                <p className="mt-0.5 text-xs text-fg-2">{s.vendor}</p>
                <p className="mt-3 text-xs text-fg-2">{s.detail}</p>
              </div>
            ))}
          </div>
        </Card>

        {dataQuality.map((q) => (
          <Card key={q.label} as="div" className="col-span-3 p-5">
            <div className="flex items-center gap-1.5">
              <p className="text-xs font-medium text-fg-2">{q.label}</p>
              <HowCalculated label={q.label}>{q.hint}</HowCalculated>
            </div>
            <p className="num mt-2 text-2xl font-semibold text-fg">{q.value}</p>
            <p className={cx('mt-1 inline-flex items-center gap-1 text-xs font-medium', q.tone === 'good' ? 'text-risk-low' : 'text-risk-med')}>
              {q.tone === 'good' ? <CheckCircle2 size={12} aria-hidden /> : <XCircle size={12} aria-hidden />}
              {q.tone === 'good' ? 'Healthy' : 'Needs attention'}
            </p>
          </Card>
        ))}

        <Card className="col-span-7">
          <CardHeader title="Schema mapping" subtitle="How source fields map to the fields the agents expect" />
          <DataTable
            caption="Schema mapping"
            dense
            rows={mappings}
            rowKey={(r) => `${r.source}-${r.field}`}
            columns={[
              { key: 'src', header: 'Source', render: (r) => r.source },
              { key: 'field', header: 'Source field', mono: true, render: (r) => r.field },
              {
                key: 'canon',
                header: 'Maps to',
                render: (r) => (
                  <Select
                    label={`Canonical field for ${r.field}`}
                    value={r.canonical}
                    onChange={(v) => {
                      setMappings((m) => m.map((x) => (x === r ? { ...x, canonical: v, match: 'OK' as const } : x)))
                      toast({ tone: 'success', title: 'Mapping updated', body: `${r.field} → ${v}. Applies from the next run.` })
                    }}
                    options={canonicalFields.map((f) => ({ value: f, label: f }))}
                  />
                ),
              },
              {
                key: 'match',
                header: 'Match',
                render: (r) => <StatusPill status={r.match === 'Needs review' ? 'Warning' : 'OK'} label={r.match} />,
              },
            ]}
          />
        </Card>

        <Card className="col-span-5">
          <CardHeader title="Run history" subtitle="Last five scheduled runs" />
          <ul className="px-5 pb-4">
            {runHistory.map((r) => (
              <li key={r.id} className="flex items-start gap-3 border-b border-line py-3 last:border-0">
                <span aria-hidden className={cx('mt-0.5', r.status === 'OK' ? 'text-risk-low' : 'text-risk-high')}>
                  {r.status === 'OK' ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-fg">
                    {r.started} <span className="font-mono text-xs font-normal text-fg-2">{r.id}</span>
                  </p>
                  <p className="text-xs text-fg-2">{r.note}</p>
                </div>
                <span className="num text-xs text-fg-2">{r.duration}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </>
  )
}
