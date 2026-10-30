import { CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { Link } from 'react-router'
import { useApp } from '@/state/AppState'
import { cx } from './ui'

export default function ToastStack() {
  const { state, dismissToast } = useApp()
  return (
    <div aria-live="polite" className="pointer-events-none fixed right-6 bottom-6 z-[60] flex w-[380px] flex-col gap-2">
      {state.toasts.map((t) => (
        <div key={t.id} role="status" className="anim-pop pointer-events-auto flex items-start gap-3 rounded-md border border-line bg-raised px-4 py-3 shadow-[var(--shadow)]">
          <span aria-hidden className={cx('mt-0.5', t.tone === 'success' ? 'text-risk-low' : t.tone === 'error' ? 'text-risk-high' : 'text-accent')}>
            {t.tone === 'success' ? <CheckCircle2 size={16} /> : t.tone === 'error' ? <XCircle size={16} /> : <Info size={16} />}
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-fg">{t.title}</p>
            {t.body && <p className="mt-0.5 text-xs text-fg-2">{t.body}</p>}
            {t.action && (
              <Link to={t.action.to} onClick={() => dismissToast(t.id)} className="mt-1.5 inline-block text-xs font-semibold text-accent hover:underline">
                {t.action.label}
              </Link>
            )}
          </div>
          <button type="button" aria-label="Dismiss notification" onClick={() => dismissToast(t.id)} className="rounded p-0.5 text-fg-2 hover:text-fg">
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}
