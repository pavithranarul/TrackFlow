import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import type { IssueStatus, Priority, Role, IssueType } from '../lib/types'

/* ------------------------------------------------------------------ utils */

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(' ')
}

/** "3 minutes ago" / "on 4 Mar" — kept short enough for dense timelines. */
export function timeAgo(iso: string): string {
  const then = new Date(iso).getTime()
  const seconds = Math.round((Date.now() - then) / 1000)

  if (seconds < 45) return 'just now'
  const units: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, 'second'],
    [3600, 'minute'],
    [86400, 'hour'],
    [604800, 'day'],
  ]
  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' })

  for (let i = 0; i < units.length; i++) {
    const [limit, unit] = units[i]
    if (seconds < limit) {
      const divisor = i === 0 ? 1 : units[i - 1][0]
      return formatter.format(-Math.round(seconds / divisor), unit)
    }
  }
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

/* ----------------------------------------------------------------- button */

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
  loading?: boolean
}

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const variants = {
    primary:
      'bg-[var(--color-accent)] text-white hover:brightness-110 active:brightness-95 shadow-sm',
    secondary:
      'bg-[var(--color-surface)] text-[var(--color-ink)] border border-[var(--color-line)] hover:bg-[var(--color-canvas)]',
    ghost: 'text-[var(--color-muted)] hover:bg-[var(--color-accent-soft)] hover:text-[var(--color-ink)]',
    danger: 'bg-rose-600 text-white hover:bg-rose-500 shadow-sm',
  }

  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={cx(
        'inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-all',
        'disabled:opacity-50 disabled:pointer-events-none',
        size === 'sm' ? 'h-7 px-2.5 text-[13px]' : 'h-9 px-3.5 text-sm',
        variants[variant],
        className,
      )}
    >
      {loading && <Spinner />}
      {children}
    </button>
  )
}

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cx('animate-spin h-3.5 w-3.5', className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
      <path
        d="M22 12a10 10 0 0 1-10 10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  )
}

/* ------------------------------------------------------------------ input */

const controlBase =
  'rounded-lg bg-[var(--color-surface)] border border-[var(--color-line)] ' +
  'text-[var(--color-ink)] placeholder:text-[var(--color-faint)] transition-colors ' +
  'focus:border-[var(--color-accent)] focus:outline-none focus:ring-2 focus:ring-[var(--color-accent)]/20'

/** Full-width form control, for use inside <Field>. */
export const inputClass = `w-full px-3 py-2 text-sm ${controlBase}`

/** Compact, content-width control for filter bars. Kept separate rather than
 *  overriding inputClass, because two competing Tailwind width utilities on
 *  one element resolve by stylesheet order, not by which was written last. */
export const filterClass = `w-auto px-2.5 py-1.5 text-[13px] ${controlBase}`

export function Field({
  label,
  error,
  hint,
  children,
}: {
  label: string
  error?: string
  hint?: string
  children: ReactNode
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-[var(--color-ink)]">
        {label}
      </span>
      {children}
      {error ? (
        <span className="mt-1 block text-xs text-rose-500">{error}</span>
      ) : hint ? (
        <span className="mt-1 block text-xs text-[var(--color-faint)]">{hint}</span>
      ) : null}
    </label>
  )
}

/* ----------------------------------------------------------------- badges */

const PRIORITY_STYLE: Record<Priority, string> = {
  LOW: 'text-slate-500 bg-slate-500/10',
  MEDIUM: 'text-sky-600 dark:text-sky-400 bg-sky-500/10',
  HIGH: 'text-amber-600 dark:text-amber-400 bg-amber-500/10',
  URGENT: 'text-orange-600 dark:text-orange-400 bg-orange-500/10',
  CRITICAL: 'text-rose-600 dark:text-rose-400 bg-rose-500/10',
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  const bars = { LOW: 1, MEDIUM: 2, HIGH: 3, URGENT: 4, CRITICAL: 5 }[priority]

  return (
    <span
      title={`Priority: ${priority.toLowerCase()}`}
      className={cx(
        'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-semibold tracking-wide',
        PRIORITY_STYLE[priority],
      )}
    >
      <span className="flex items-end gap-[1.5px]" aria-hidden>
        {[1, 2, 3, 4, 5].map((n) => (
          <span
            key={n}
            className={cx('w-[2.5px] rounded-sm bg-current', n <= bars ? 'opacity-100' : 'opacity-25')}
            style={{ height: `${3 + n * 1.4}px` }}
          />
        ))}
      </span>
      {priority}
    </span>
  )
}

const TYPE_META: Record<IssueType, { icon: string; className: string }> = {
  BUG: { icon: '●', className: 'text-rose-500' },
  FEATURE: { icon: '◆', className: 'text-violet-500' },
  CHORE: { icon: '○', className: 'text-slate-400' },
  TASK: { icon: '■', className: 'text-sky-500' },
}

export function TypeIcon({ type }: { type: IssueType }) {
  const meta = TYPE_META[type]
  return (
    <span title={type.toLowerCase()} className={cx('text-[10px] leading-none', meta.className)}>
      {meta.icon}
    </span>
  )
}

const STATUS_STYLE: Record<IssueStatus, string> = {
  TODO: 'bg-slate-500/12 text-slate-600 dark:text-slate-300',
  IN_PROGRESS: 'bg-amber-500/15 text-amber-700 dark:text-amber-400',
  TESTING: 'bg-violet-500/15 text-violet-700 dark:text-violet-400',
  DONE: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400',
}

export function StatusBadge({ status }: { status: IssueStatus }) {
  const label = { TODO: 'To Do', IN_PROGRESS: 'In Progress', TESTING: 'Testing', DONE: 'Done' }[
    status
  ]
  return (
    <span
      className={cx(
        'inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold',
        STATUS_STYLE[status],
      )}
    >
      {label}
    </span>
  )
}

const ROLE_STYLE: Record<Role, string> = {
  OWNER: 'bg-[var(--color-accent)]/15 text-[var(--color-accent)]',
  MANAGER: 'bg-teal-500/15 text-teal-700 dark:text-teal-400',
  DEVELOPER: 'bg-sky-500/15 text-sky-700 dark:text-sky-400',
  VIEWER: 'bg-slate-500/12 text-slate-600 dark:text-slate-300',
}

export function RoleBadge({ role }: { role: Role }) {
  return (
    <span
      className={cx(
        'inline-flex rounded-md px-2 py-0.5 text-[11px] font-semibold',
        ROLE_STYLE[role],
      )}
    >
      {role[0] + role.slice(1).toLowerCase()}
    </span>
  )
}

/* ----------------------------------------------------------------- avatar */

const AVATAR_COLORS = [
  'bg-rose-500',
  'bg-orange-500',
  'bg-amber-500',
  'bg-emerald-500',
  'bg-teal-500',
  'bg-sky-500',
  'bg-indigo-500',
  'bg-violet-500',
  'bg-fuchsia-500',
]

export function Avatar({
  name,
  size = 24,
  title,
}: {
  name: string | null | undefined
  size?: number
  title?: string
}) {
  if (!name) {
    return (
      <span
        title={title ?? 'Unassigned'}
        style={{ width: size, height: size }}
        className="inline-flex shrink-0 items-center justify-center rounded-full border border-dashed border-[var(--color-line)] text-[var(--color-faint)]"
      >
        <svg viewBox="0 0 24 24" width={size * 0.55} height={size * 0.55} fill="none" aria-hidden>
          <circle cx="12" cy="8" r="3.4" stroke="currentColor" strokeWidth="2" />
          <path d="M4.5 20a7.5 7.5 0 0 1 15 0" stroke="currentColor" strokeWidth="2" />
        </svg>
      </span>
    )
  }

  let hash = 0
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) >>> 0

  return (
    <span
      title={title ?? name}
      style={{ width: size, height: size, fontSize: size * 0.42 }}
      className={cx(
        'inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white select-none',
        AVATAR_COLORS[hash % AVATAR_COLORS.length],
      )}
    >
      {name.slice(0, 2).toUpperCase()}
    </span>
  )
}

/* ------------------------------------------------------------------ modal */

export function Modal({
  open,
  onClose,
  title,
  children,
  width = 'max-w-lg',
}: {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  width?: string
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto p-4 pt-[10vh]">
      <div
        className="fixed inset-0 bg-black/40 backdrop-blur-[2px]"
        onClick={onClose}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cx(
          'animate-fade-up relative w-full rounded-xl border border-[var(--color-line)] bg-[var(--color-raised)] shadow-2xl',
          width,
        )}
      >
        <div className="flex items-center justify-between border-b border-[var(--color-line)] px-5 py-3.5">
          <h2 className="text-sm font-semibold">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-md p-1 text-[var(--color-faint)] transition-colors hover:bg-[var(--color-canvas)] hover:text-[var(--color-ink)]"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden>
              <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ toast */

type Toast = { id: number; message: string; tone: 'error' | 'success' }
const ToastContext = createContext<(message: string, tone?: Toast['tone']) => void>(() => {})

export function useToast() {
  return useContext(ToastContext)
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const push = useCallback((message: string, tone: Toast['tone'] = 'error') => {
    const id = nextId.current++
    setToasts((current) => [...current, { id, message, tone }])
    setTimeout(() => setToasts((current) => current.filter((t) => t.id !== id)), 5000)
  }, [])

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="fixed bottom-5 right-5 z-[100] flex flex-col gap-2" role="status" aria-live="polite">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cx(
              'animate-slide-in flex max-w-sm items-start gap-2.5 rounded-lg border px-3.5 py-2.5 text-sm shadow-lg',
              toast.tone === 'error'
                ? 'border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300 backdrop-blur'
                : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 backdrop-blur',
            )}
          >
            <span className="mt-px shrink-0">{toast.tone === 'error' ? '⚠' : '✓'}</span>
            <span>{toast.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

/* ------------------------------------------------------- states & helpers */

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string
  hint?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--color-line)] px-6 py-14 text-center">
      <p className="text-sm font-medium text-[var(--color-ink)]">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-[13px] text-[var(--color-muted)]">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('skeleton rounded-md', className)} />
}

/* Debounce a fast-changing value (search boxes). */
export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

/* Theme, persisted and applied to <html>. */
export function useTheme() {
  const [dark, setDark] = useState(
    () => document.documentElement.classList.contains('dark'),
  )

  const toggle = useCallback(() => {
    setDark((current) => {
      const next = !current
      document.documentElement.classList.toggle('dark', next)
      localStorage.setItem('trackflow.theme', next ? 'dark' : 'light')
      return next
    })
  }, [])

  return useMemo(() => ({ dark, toggle }), [dark, toggle])
}
