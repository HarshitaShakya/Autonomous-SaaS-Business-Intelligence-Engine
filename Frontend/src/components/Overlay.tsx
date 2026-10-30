import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { Button, cx } from './ui'

const FOCUSABLE = 'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

function useFocusTrap(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose
  useEffect(() => {
    if (!open) return
    const prev = document.activeElement as HTMLElement | null
    const el = ref.current
    const first = el?.querySelector<HTMLElement>('[data-autofocus]') ?? el?.querySelector<HTMLElement>(FOCUSABLE)
    first?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        closeRef.current()
        return
      }
      if (e.key !== 'Tab' || !el) return
      const items = Array.from(el.querySelectorAll<HTMLElement>(FOCUSABLE))
      if (!items.length) return
      const a = items[0]
      const b = items[items.length - 1]
      if (e.shiftKey && document.activeElement === a) {
        e.preventDefault()
        b.focus()
      } else if (!e.shiftKey && document.activeElement === b) {
        e.preventDefault()
        a.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = overflow
      prev?.focus?.()
    }
  }, [open])
  return ref
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  width = 520,
  tone,
}: {
  open: boolean
  onClose: () => void
  title: ReactNode
  description?: ReactNode
  children?: ReactNode
  footer?: ReactNode
  width?: number
  tone?: 'warning'
}) {
  const ref = useFocusTrap(open, onClose)
  const titleId = useId()
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6">
      <div className="absolute inset-0 bg-[var(--overlay)]" onClick={onClose} aria-hidden />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={{ width }}
        className={cx('anim-pop relative max-h-[85vh] overflow-auto rounded-card border bg-surface shadow-[var(--shadow)]', tone === 'warning' ? 'border-risk-med/50' : 'border-line')}
      >
        <div className="flex items-start justify-between gap-4 px-6 pt-5">
          <div>
            <h2 id={titleId} className="text-lg font-semibold text-fg">
              {title}
            </h2>
            {description && <div className="mt-1 text-sm text-fg-2">{description}</div>}
          </div>
          <Button variant="ghost" size="sm" aria-label="Close dialog" onClick={onClose} icon={<X size={16} />} />
        </div>
        {children && <div className="px-6 pt-4">{children}</div>}
        {footer && <div className="mt-6 flex items-center justify-end gap-2 border-t border-line px-6 py-4">{footer}</div>}
        {!footer && <div className="h-6" />}
      </div>
    </div>,
    document.body,
  )
}

export function Drawer({ open, onClose, title, subtitle, children, width = 480 }: { open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode; children: ReactNode; width?: number }) {
  const ref = useFocusTrap(open, onClose)
  const titleId = useId()
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-[var(--overlay)]" onClick={onClose} aria-hidden />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={{ width }}
        className="anim-slide absolute top-0 right-0 flex h-full flex-col border-l border-line bg-surface shadow-[var(--shadow)]"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-6 py-5">
          <div className="min-w-0">
            <h2 id={titleId} className="text-lg font-semibold text-fg">
              {title}
            </h2>
            {subtitle && <div className="mt-1 text-sm text-fg-2">{subtitle}</div>}
          </div>
          <Button variant="ghost" size="sm" aria-label="Close panel" onClick={onClose} icon={<X size={16} />} />
        </div>
        <div className="flex-1 overflow-auto px-6 py-5">{children}</div>
      </div>
    </div>,
    document.body,
  )
}
