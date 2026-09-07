import { useState, type FormEvent } from 'react'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import { Button, Field, inputClass, useTheme } from '../components/ui'

export default function Login() {
  const { signIn, register } = useAuth()
  const { dark, toggle } = useTheme()

  const [mode, setMode] = useState<'signin' | 'register'>('signin')
  const [form, setForm] = useState({
    username: '',
    password: '',
    password_confirm: '',
    email: '',
    first_name: '',
    last_name: '',
  })
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const [busy, setBusy] = useState(false)

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: event.target.value }))

  const fieldError = (key: string) => errors[key]?.[0]

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setErrors({})
    setBusy(true)

    try {
      if (mode === 'signin') {
        await signIn(form.username, form.password)
      } else {
        await register({
          username: form.username,
          email: form.email,
          password: form.password,
          password_confirm: form.password_confirm,
          first_name: form.first_name,
          last_name: form.last_name,
        })
      }
    } catch (error) {
      if (error instanceof ApiError) {
        setErrors(
          Object.keys(error.fields).length
            ? error.fields
            : { detail: [error.message] },
        )
      } else {
        setErrors({ detail: ['Could not reach the server. Is Django running?'] })
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen">
      {/* Brand panel — hidden on small screens where it would just push the
          form below the fold. */}
      <div className="relative hidden w-[46%] flex-col justify-between overflow-hidden bg-[var(--color-accent)] p-10 text-white lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-25"
          style={{
            backgroundImage:
              'radial-gradient(circle at 20% 20%, rgba(255,255,255,.5) 0, transparent 45%), radial-gradient(circle at 80% 70%, rgba(255,255,255,.35) 0, transparent 40%)',
          }}
          aria-hidden
        />
        <div className="relative flex items-center gap-2.5">
          <Logo className="h-7 w-7" />
          <span className="text-lg font-semibold tracking-tight">TrackFlow</span>
        </div>

        <div className="relative">
          <h1 className="max-w-md text-[2.6rem] leading-[1.1] font-semibold tracking-tight">
            Track the work, not the paperwork.
          </h1>
          <p className="mt-4 max-w-sm text-[15px] leading-relaxed text-white/75">
            Projects, roles, and an issue workflow that actually enforces itself —
            every status change checked against the transition graph and written
            to an audit trail.
          </p>
        </div>

        <div className="relative flex gap-6 text-[13px] text-white/70">
          <span>Role-based access</span>
          <span>Enforced workflow</span>
          <span>Full audit trail</span>
        </div>
      </div>

      {/* Form panel */}
      <div className="flex flex-1 flex-col">
        <div className="flex justify-end p-4">
          <button
            onClick={toggle}
            aria-label="Toggle theme"
            className="rounded-lg p-2 text-[var(--color-muted)] transition-colors hover:bg-[var(--color-surface)] hover:text-[var(--color-ink)]"
          >
            {dark ? <SunIcon /> : <MoonIcon />}
          </button>
        </div>

        <div className="flex flex-1 items-center justify-center px-6 pb-16">
          <form onSubmit={onSubmit} className="w-full max-w-sm">
            <div className="mb-7 flex items-center gap-2.5 lg:hidden">
              <Logo className="h-7 w-7 text-[var(--color-accent)]" />
              <span className="text-lg font-semibold tracking-tight">TrackFlow</span>
            </div>

            <h2 className="text-xl font-semibold tracking-tight">
              {mode === 'signin' ? 'Sign in' : 'Create your account'}
            </h2>
            <p className="mt-1 mb-6 text-[13px] text-[var(--color-muted)]">
              {mode === 'signin'
                ? 'Enter your credentials to continue.'
                : 'Pick a username and a strong password.'}
            </p>

            <div className="space-y-3.5">
              <Field label="Username" error={fieldError('username')}>
                <input
                  className={inputClass}
                  value={form.username}
                  onChange={set('username')}
                  autoComplete="username"
                  autoFocus
                  required
                />
              </Field>

              {mode === 'register' && (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="First name" error={fieldError('first_name')}>
                      <input className={inputClass} value={form.first_name} onChange={set('first_name')} />
                    </Field>
                    <Field label="Last name" error={fieldError('last_name')}>
                      <input className={inputClass} value={form.last_name} onChange={set('last_name')} />
                    </Field>
                  </div>
                  <Field label="Email" error={fieldError('email')}>
                    <input
                      type="email"
                      className={inputClass}
                      value={form.email}
                      onChange={set('email')}
                      autoComplete="email"
                    />
                  </Field>
                </>
              )}

              <Field label="Password" error={fieldError('password')}>
                <input
                  type="password"
                  className={inputClass}
                  value={form.password}
                  onChange={set('password')}
                  autoComplete={mode === 'signin' ? 'current-password' : 'new-password'}
                  required
                />
              </Field>

              {mode === 'register' && (
                <Field label="Confirm password" error={fieldError('password_confirm')}>
                  <input
                    type="password"
                    className={inputClass}
                    value={form.password_confirm}
                    onChange={set('password_confirm')}
                    autoComplete="new-password"
                    required
                  />
                </Field>
              )}
            </div>

            {(errors.detail || errors.non_field_errors) && (
              <p className="mt-4 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-[13px] text-rose-600 dark:text-rose-400">
                {(errors.detail ?? errors.non_field_errors)[0]}
              </p>
            )}

            <Button type="submit" variant="primary" loading={busy} className="mt-6 w-full">
              {mode === 'signin' ? 'Sign in' : 'Create account'}
            </Button>

            <p className="mt-4 text-center text-[13px] text-[var(--color-muted)]">
              {mode === 'signin' ? "Don't have an account? " : 'Already have one? '}
              <button
                type="button"
                onClick={() => {
                  setMode(mode === 'signin' ? 'register' : 'signin')
                  setErrors({})
                }}
                className="font-medium text-[var(--color-accent)] hover:underline"
              >
                {mode === 'signin' ? 'Register' : 'Sign in'}
              </button>
            </p>

            <div className="mt-8 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] px-3.5 py-3 text-[12px] text-[var(--color-muted)]">
              <span className="font-medium text-[var(--color-ink)]">Demo data?</span> Run{' '}
              <code className="rounded bg-[var(--color-canvas)] px-1 py-0.5 font-mono text-[11px]">
                manage.py seed_demo
              </code>{' '}
              then sign in as <code className="font-mono text-[11px]">ada</code> /{' '}
              <code className="font-mono text-[11px]">demo-passw0rd!</code>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="none" aria-hidden>
      <rect width="100" height="100" rx="24" fill="currentColor" opacity="0.18" />
      <path
        d="M26 34h48M26 50h32M26 66h40"
        stroke="currentColor"
        strokeWidth="9"
        strokeLinecap="round"
      />
    </svg>
  )
}

function SunIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden>
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="2" />
      <path
        d="M12 2v2m0 16v2M2 12h2m16 0h2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden>
      <path
        d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export { SunIcon, MoonIcon }
