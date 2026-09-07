import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../lib/auth'
import { useProjects } from '../lib/queries'
import { Avatar, cx, Skeleton, useTheme } from './ui'
import { Logo, MoonIcon, SunIcon } from '../pages/Login'

export default function Layout() {
  const { user, signOut } = useAuth()
  const { dark, toggle } = useTheme()
  const navigate = useNavigate()
  const { data: projects, isLoading } = useProjects({ ordering: 'name' })

  const [menuOpen, setMenuOpen] = useState(false)
  const [navOpen, setNavOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const onClick = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [menuOpen])

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    cx(
      'flex items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-[13px] font-medium transition-colors',
      isActive
        ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
        : 'text-[var(--color-muted)] hover:bg-[var(--color-surface)] hover:text-[var(--color-ink)]',
    )

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile scrim */}
      {navOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          onClick={() => setNavOpen(false)}
          aria-hidden
        />
      )}

      <aside
        className={cx(
          'fixed inset-y-0 left-0 z-40 flex w-60 shrink-0 flex-col border-r border-[var(--color-line)] bg-[var(--color-surface)] transition-transform lg:static lg:translate-x-0',
          navOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center gap-2.5 px-4 py-4">
          <Logo className="h-6 w-6 text-[var(--color-accent)]" />
          <span className="font-semibold tracking-tight">TrackFlow</span>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 pb-4">
          <div className="space-y-0.5">
            <NavLink to="/issues" className={linkClass} onClick={() => setNavOpen(false)}>
              <InboxIcon /> My issues
            </NavLink>
            <NavLink to="/projects" end className={linkClass} onClick={() => setNavOpen(false)}>
              <GridIcon /> All projects
            </NavLink>
            <NavLink to="/organizations" className={linkClass} onClick={() => setNavOpen(false)}>
              <BuildingIcon /> Organizations
            </NavLink>
          </div>

          <p className="mt-6 mb-1.5 px-2.5 text-[11px] font-semibold tracking-wider text-[var(--color-faint)] uppercase">
            Projects
          </p>

          <div className="space-y-0.5">
            {isLoading &&
              [0, 1, 2].map((n) => <Skeleton key={n} className="mx-1 my-1.5 h-5" />)}

            {projects?.results.map((project) => (
              <NavLink
                key={project.id}
                to={`/projects/${project.id}`}
                className={linkClass}
                onClick={() => setNavOpen(false)}
              >
                <span className="flex h-4.5 w-6 shrink-0 items-center justify-center rounded bg-[var(--color-canvas)] text-[9px] font-bold tracking-tight text-[var(--color-muted)]">
                  {project.key.slice(0, 3)}
                </span>
                <span className="truncate">{project.name}</span>
              </NavLink>
            ))}

            {projects?.results.length === 0 && (
              <p className="px-2.5 py-1 text-[12px] text-[var(--color-faint)]">
                No projects yet.
              </p>
            )}
          </div>
        </nav>

        {/* Account */}
        <div ref={menuRef} className="relative border-t border-[var(--color-line)] p-3">
          {menuOpen && (
            <div className="animate-fade-up absolute bottom-full left-3 right-3 mb-1 overflow-hidden rounded-lg border border-[var(--color-line)] bg-[var(--color-raised)] shadow-lg">
              <button
                onClick={() => {
                  toggle()
                  setMenuOpen(false)
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-[13px] text-[var(--color-ink)] transition-colors hover:bg-[var(--color-canvas)]"
              >
                {dark ? <SunIcon /> : <MoonIcon />}
                {dark ? 'Light theme' : 'Dark theme'}
              </button>
              <button
                onClick={() => {
                  signOut()
                  navigate('/')
                }}
                className="flex w-full items-center gap-2 px-3 py-2 text-[13px] text-rose-500 transition-colors hover:bg-[var(--color-canvas)]"
              >
                <SignOutIcon /> Sign out
              </button>
            </div>
          )}

          <button
            onClick={() => setMenuOpen((open) => !open)}
            className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 transition-colors hover:bg-[var(--color-canvas)]"
          >
            <Avatar name={user?.username} size={26} />
            <span className="min-w-0 flex-1 text-left">
              <span className="block truncate text-[13px] font-medium">
                {user?.first_name || user?.username}
              </span>
              <span className="block truncate text-[11px] text-[var(--color-faint)]">
                @{user?.username}
              </span>
            </span>
            <ChevronIcon className="shrink-0 text-[var(--color-faint)]" />
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <button
          onClick={() => setNavOpen(true)}
          aria-label="Open navigation"
          className="absolute left-3 top-3 z-20 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] p-2 lg:hidden"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden>
            <path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>

        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function InboxIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden>
      <path
        d="M3 13h4l1.5 3h7L17 13h4M3 13l2.5-7h13L21 13v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5Z"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function BuildingIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden>
      <path d="M3 21h18M5 21V5a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v16M15 21V10h2a2 2 0 0 1 2 2v9" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M9 7h2M9 11h2M9 15h2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  )
}

function GridIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden>
      <rect x="3" y="3" width="7.5" height="7.5" rx="2" stroke="currentColor" strokeWidth="1.9" />
      <rect x="13.5" y="3" width="7.5" height="7.5" rx="2" stroke="currentColor" strokeWidth="1.9" />
      <rect x="3" y="13.5" width="7.5" height="7.5" rx="2" stroke="currentColor" strokeWidth="1.9" />
      <rect x="13.5" y="13.5" width="7.5" height="7.5" rx="2" stroke="currentColor" strokeWidth="1.9" />
    </svg>
  )
}

function SignOutIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden>
      <path
        d="M15 17l5-5-5-5M20 12H9M12 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h6"
        stroke="currentColor"
        strokeWidth="1.9"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" className={className} aria-hidden>
      <path d="M7 15l5-5 5 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function PageHeader({
  title,
  subtitle,
  actions,
  children,
}: {
  title: React.ReactNode
  subtitle?: React.ReactNode
  actions?: React.ReactNode
  children?: React.ReactNode
}) {
  return (
    <div className="sticky top-0 z-10 border-b border-[var(--color-line)] bg-[var(--color-canvas)]/85 backdrop-blur">
      <div className="flex flex-wrap items-center gap-3 px-5 py-4 pl-14 lg:pl-5">
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-semibold tracking-tight">{title}</h1>
          {subtitle && (
            <p className="mt-0.5 truncate text-[13px] text-[var(--color-muted)]">{subtitle}</p>
          )}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  )
}
