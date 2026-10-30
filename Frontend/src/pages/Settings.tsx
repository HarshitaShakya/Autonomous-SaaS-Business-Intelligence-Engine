import { useState } from 'react'
import { NavLink, useParams, Navigate } from 'react-router'
import { Bell, Eye, EyeOff, Gauge, Lock, Plug, ShieldCheck, Users } from 'lucide-react'
import { approvers, integrations, thresholds } from '@/data/mock'
import { useApp } from '@/state/AppState'
import { Button, Card, CardHeader, PageHeader, Select, StatusPill, Switch, cx } from '@/components/ui'

const sections = [
  { id: 'approvals', label: 'Approval rules', icon: ShieldCheck },
  { id: 'thresholds', label: 'Thresholds', icon: Gauge },
  { id: 'integrations', label: 'Integrations', icon: Plug },
  { id: 'users', label: 'Users & roles', icon: Users },
  { id: 'notifications', label: 'Notifications', icon: Bell },
]

function Approvals() {
  const { toast } = useApp()
  const [roles, setRoles] = useState<Record<string, string>>({ 'UI guide': 'approver', 'Targeted email': 'approver', 'A/B test': 'approver', 'Pricing change': 'admin' })
  return (
    <Card>
      <CardHeader title="Approval rules" subtitle="Who must sign off before the Action agent runs anything" />
      <div className="space-y-5 px-5 pb-5">
        <div className="flex items-center gap-4 rounded-md border border-line bg-raised/50 p-4">
          <Lock size={16} className="text-fg-2" aria-hidden />
          <div className="flex-1">
            <p className="text-sm font-semibold text-fg">Require human approval for every action</p>
            <p className="text-xs text-fg-2">Always on. Agents can recommend but never act on their own.</p>
          </div>
          <Switch checked disabled label="Require human approval (locked on)" description="Locked on by your organization's policy" />
        </div>
        <div>
          <p className="mb-2 text-sm font-semibold text-fg">Who can approve each action type</p>
          <ul className="divide-y divide-line rounded-md border border-line">
            {Object.entries(roles).map(([type, role]) => (
              <li key={type} className="flex items-center justify-between px-4 py-3">
                <span className="text-sm text-fg">{type}</span>
                <Select
                  label={`Approver role for ${type}`}
                  value={role}
                  onChange={(v) => {
                    setRoles((r) => ({ ...r, [type]: v }))
                    toast({ tone: 'success', title: 'Approval rule saved', body: `${type} now needs ${v === 'admin' ? 'an Admin' : v === 'two' ? 'two approvers' : 'any Approver'}.` })
                  }}
                  options={[
                    { value: 'approver', label: 'Any Approver' },
                    { value: 'admin', label: 'Admin only' },
                    { value: 'two', label: 'Two approvers' },
                  ]}
                />
              </li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  )
}

function Thresholds() {
  const { toast } = useApp()
  const [high, setHigh] = useState(thresholds.high)
  const [med, setMed] = useState(thresholds.medium)
  const [win, setWin] = useState(thresholds.windowDays)
  const invalid = med >= high || med < 1 || high > 99
  const field = (label: string, value: number, set: (n: number) => void, suffix: string, hint: string) => (
    <label className="block">
      <span className="text-sm font-medium text-fg">{label}</span>
      <span className="mt-0.5 block text-xs text-fg-2">{hint}</span>
      <span className="mt-2 flex items-center gap-2">
        <input type="number" value={value} onChange={(e) => set(Number(e.target.value))} className="num h-9 w-24 rounded-md border border-line bg-canvas px-3 text-sm text-fg" />
        <span className="text-sm text-fg-2">{suffix}</span>
      </span>
    </label>
  )
  return (
    <Card>
      <CardHeader title="Risk thresholds" subtitle="Where we draw the line between high, medium and low risk" />
      <div className="grid grid-cols-3 gap-6 px-5 pb-5">
        {field('High risk at or above', high, setHigh, '%', 'Chance of cancelling')}
        {field('Medium risk at or above', med, setMed, '%', 'Below this is low risk')}
        {field('Churn window', win, setWin, 'days', 'How far ahead we predict')}
      </div>
      <div className="flex items-center gap-3 border-t border-line px-5 py-4">
        {invalid && <p className="text-xs text-risk-high">Medium must be lower than high, between 1 and 99.</p>}
        <Button className="ml-auto" variant="primary" disabled={invalid} onClick={() => toast({ tone: 'success', title: 'Thresholds saved', body: 'They apply from the next analysis run.' })}>
          Save
        </Button>
      </div>
    </Card>
  )
}

function Integrations() {
  const { toast } = useApp()
  const [items, setItems] = useState(integrations)
  const [revealed, setRevealed] = useState<string | null>(null)
  return (
    <div className="grid grid-cols-2 gap-4">
      {items.map((it) => (
        <Card key={it.name} as="div" className="p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-fg">{it.name}</p>
              <p className="text-xs text-fg-2">{it.purpose}</p>
            </div>
            <StatusPill status="OK" label={it.status} />
          </div>
          <div className="mt-4 flex items-center gap-2 rounded-md border border-line bg-canvas px-3 py-2">
            <span className="flex-1 truncate font-mono text-xs text-fg">{revealed === it.name ? it.credential : `${it.credential.slice(0, it.credential.indexOf('_', 3) + 1 || 3)}••••${it.credential.slice(-4)}`}</span>
            <button
              type="button"
              onClick={() => setRevealed((r) => (r === it.name ? null : it.name))}
              aria-label={revealed === it.name ? `Hide ${it.name} credential` : `Reveal ${it.name} credential`}
              className="rounded p-1 text-fg-2 hover:text-fg"
            >
              {revealed === it.name ? <EyeOff size={14} /> : <Eye size={14} />}
            </button>
          </div>
          <div className="mt-4 flex items-center justify-between">
            <span className="text-xs text-fg-2">
              Sends to: <span className="font-semibold text-fg">{it.live ? 'Live' : 'Mock'}</span>
            </span>
            <span className="flex items-center gap-2 text-xs text-fg-2">
              Mock
              <Switch
                checked={it.live}
                label={`${it.name}: use live connection`}
                onChange={(v) => {
                  setItems((list) => list.map((x) => (x.name === it.name ? { ...x, live: v } : x)))
                  toast({ tone: 'info', title: `${it.name} set to ${v ? 'Live' : 'Mock'}` })
                }}
              />
              Live
            </span>
          </div>
        </Card>
      ))}
    </div>
  )
}

function UsersRoles() {
  return (
    <Card>
      <CardHeader title="Users & roles" subtitle="People who can review and approve actions" right={<Button size="sm" variant="secondary">Invite</Button>} />
      <ul className="divide-y divide-line border-t border-line">
        {approvers.map((u) => (
          <li key={u.name} className="flex items-center gap-4 px-5 py-3">
            <span className="inline-flex size-9 items-center justify-center rounded-full bg-raised text-xs font-semibold text-fg ring-1 ring-line">{u.initials}</span>
            <span className="flex-1">
              <span className="block text-sm font-medium text-fg">{u.name}</span>
              <span className="block text-xs text-fg-2">
                {u.title} · {u.email}
              </span>
            </span>
            <span className="rounded-full border border-line bg-raised px-2.5 py-0.5 text-xs font-medium text-fg-2">{u.role}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

function Notifications() {
  const [prefs, setPrefs] = useState({ emailPending: true, emailFailed: true, slackPending: false, slackFailed: true, digest: true })
  const rows: [keyof typeof prefs, string, string][] = [
    ['emailPending', 'Email me when new recommendations need a decision', 'Email'],
    ['emailFailed', 'Email me when an action fails', 'Email'],
    ['slackPending', 'Post new recommendations to #growth-alerts', 'Slack'],
    ['slackFailed', 'Post failed actions to #growth-alerts', 'Slack'],
    ['digest', 'Weekly impact digest every Monday', 'Email'],
  ]
  return (
    <Card>
      <CardHeader title="Notifications" subtitle="How you hear about decisions and problems" />
      <ul className="divide-y divide-line border-t border-line">
        {rows.map(([k, label, ch]) => (
          <li key={k} className="flex items-center gap-4 px-5 py-3">
            <span className="w-12 text-xs text-fg-2">{ch}</span>
            <span className="flex-1 text-sm text-fg">{label}</span>
            <Switch checked={prefs[k]} label={label} onChange={(v) => setPrefs((p) => ({ ...p, [k]: v }))} />
          </li>
        ))}
      </ul>
    </Card>
  )
}

export default function SettingsPage() {
  const { section } = useParams()
  if (!section) return <Navigate to="/settings/approvals" replace />
  const current = sections.find((s) => s.id === section)
  if (!current) return <Navigate to="/settings/approvals" replace />
  return (
    <>
      <PageHeader title="Settings" description="Guardrails, thresholds and connections for the agents." />
      <nav className="col-span-3" aria-label="Settings sections">
        <ul className="space-y-1">
          {sections.map((s) => (
            <li key={s.id}>
              <NavLink
                to={`/settings/${s.id}`}
                className={({ isActive }) => cx('flex h-9 items-center gap-3 rounded-md px-3 text-sm font-medium', isActive ? 'bg-raised text-fg' : 'text-fg-2 hover:bg-raised/60 hover:text-fg')}
              >
                <s.icon size={16} strokeWidth={1.5} aria-hidden />
                {s.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
      <div className="col-span-9">
        {section === 'approvals' && <Approvals />}
        {section === 'thresholds' && <Thresholds />}
        {section === 'integrations' && <Integrations />}
        {section === 'users' && <UsersRoles />}
        {section === 'notifications' && <Notifications />}
      </div>
    </>
  )
}
