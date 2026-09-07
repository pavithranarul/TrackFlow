import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../lib/api'
import { useCreateProject, useOrganizations, useProjects } from '../lib/queries'
import { PageHeader } from '../components/Layout'
import {
  Button,
  cx,
  EmptyState,
  Field,
  filterClass,
  inputClass,
  Modal,
  Skeleton,
  timeAgo,
  useDebounced,
  useToast,
} from '../components/ui'

export default function Projects() {
  const [search, setSearch] = useState('')
  const [visibility, setVisibility] = useState('')
  const [status, setStatus] = useState('ACTIVE')
  const [creating, setCreating] = useState(false)

  const debounced = useDebounced(search)
  const { data, isLoading } = useProjects({
    search: debounced,
    visibility,
    status,
    ordering: 'name',
  })

  return (
    <>
      <PageHeader
        title="Projects"
        subtitle={
          data ? `${data.count} project${data.count === 1 ? '' : 's'} you can see` : undefined
        }
        actions={
          <Button variant="primary" onClick={() => setCreating(true)}>
            <PlusIcon /> New project
          </Button>
        }
      >
        <div className="flex flex-wrap gap-2 px-5 pb-3">
          <div className="relative min-w-[220px] flex-1 sm:max-w-xs">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-[var(--color-faint)]" />
            <input
              className={cx(inputClass, 'py-1.5 pl-8 text-[13px]')}
              placeholder="Search projects…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <select
            className={filterClass}
            value={status}
            onChange={(event) => setStatus(event.target.value)}
          >
            <option value="">All statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="ARCHIVED">Archived</option>
          </select>
          <select
            className={filterClass}
            value={visibility}
            onChange={(event) => setVisibility(event.target.value)}
          >
            <option value="">Any visibility</option>
            <option value="PRIVATE">Private</option>
            <option value="PUBLIC">Public</option>
          </select>
        </div>
      </PageHeader>

      <div className="p-5">
        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {[0, 1, 2, 3, 4, 5].map((n) => (
              <Skeleton key={n} className="h-[120px]" />
            ))}
          </div>
        ) : data && data.results.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {data.results.map((project) => (
              <Link
                key={project.id}
                to={`/projects/${project.id}`}
                className="group rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4 transition-all hover:-translate-y-0.5 hover:border-[var(--color-accent)]/50 hover:shadow-md"
              >
                <div className="mb-2.5 flex items-center gap-2">
                  <span className="rounded-md bg-[var(--color-accent-soft)] px-1.5 py-0.5 font-mono text-[11px] font-bold text-[var(--color-accent)]">
                    {project.key}
                  </span>
                  {project.visibility === 'PUBLIC' && (
                    <span className="rounded-md bg-emerald-500/12 px-1.5 py-0.5 text-[11px] font-medium text-emerald-700 dark:text-emerald-400">
                      Public
                    </span>
                  )}
                  {project.status === 'ARCHIVED' && (
                    <span className="rounded-md bg-slate-500/12 px-1.5 py-0.5 text-[11px] font-medium text-[var(--color-muted)]">
                      Archived
                    </span>
                  )}
                </div>

                <h3 className="truncate font-semibold tracking-tight group-hover:text-[var(--color-accent)]">
                  {project.name}
                </h3>

                <p className="mt-2 text-[12px] text-[var(--color-faint)]">
                  {project.organization_name && (
                    <>
                      <span className="text-[var(--color-muted)]">
                        {project.organization_name}
                      </span>{' '}
                      ·{' '}
                    </>
                  )}
                  {project.owner} · updated {timeAgo(project.updated_at)}
                </p>
              </Link>
            ))}
          </div>
        ) : (
          <EmptyState
            title={debounced ? 'No projects match that search' : 'No projects yet'}
            hint={
              debounced
                ? 'Try a different name or key.'
                : 'Create one to start tracking work, or ask an owner to add you to theirs.'
            }
            action={
              !debounced && (
                <Button variant="primary" onClick={() => setCreating(true)}>
                  <PlusIcon /> New project
                </Button>
              )
            }
          />
        )}
      </div>

      <CreateProjectModal open={creating} onClose={() => setCreating(false)} />
    </>
  )
}

function CreateProjectModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateProject()
  const { data: orgs } = useOrganizations()
  const toast = useToast()

  const [form, setForm] = useState({
    name: '',
    key: '',
    description: '',
    visibility: 'PRIVATE',
    organization: '',
  })
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  // A project must live in a tenant. With exactly one to choose from, pick it
  // rather than making the user confirm the obvious.
  const options = orgs?.results.filter((o) => o.is_active) ?? []
  const organization = form.organization || (options.length === 1 ? String(options[0].id) : '')

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: event.target.value }))

  const reset = () => {
    setForm({ name: '', key: '', description: '', visibility: 'PRIVATE', organization: '' })
    setErrors({})
  }

  return (
    <Modal
      open={open}
      onClose={() => {
        reset()
        onClose()
      }}
      title="New project"
    >
      <form
        className="space-y-3.5"
        onSubmit={async (event) => {
          event.preventDefault()
          setErrors({})
          try {
            await create.mutateAsync({ ...form, organization: Number(organization) })
            toast('Project created.', 'success')
            reset()
            onClose()
          } catch (error) {
            if (error instanceof ApiError) setErrors(error.fields)
            else toast((error as Error).message)
          }
        }}
      >
        <Field label="Name" error={errors.name?.[0]}>
          <input
            className={inputClass}
            value={form.name}
            onChange={(event) => {
              const name = event.target.value
              setForm((current) => ({
                ...current,
                name,
                // Suggest a key from the name until the user types their own.
                key:
                  current.key === '' ||
                  current.key === suggestKey(current.name)
                    ? suggestKey(name)
                    : current.key,
              }))
            }}
            autoFocus
            required
          />
        </Field>

        <Field
          label="Key"
          error={errors.key?.[0]}
          hint="Short, unique, uppercase — issues become KEY-1, KEY-2…"
        >
          <input
            className={cx(inputClass, 'font-mono uppercase')}
            value={form.key}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                key: event.target.value.toUpperCase().slice(0, 10),
              }))
            }
            maxLength={10}
            required
          />
        </Field>

        <Field label="Description" error={errors.description?.[0]}>
          <textarea
            className={cx(inputClass, 'min-h-20 resize-y')}
            value={form.description}
            onChange={set('description')}
          />
        </Field>

        <Field
          label="Organization"
          error={errors.organization?.[0]}
          hint="The tenant this project belongs to. It cannot be changed later."
        >
          <select
            className={inputClass}
            value={organization}
            onChange={set('organization')}
            required
          >
            <option value="">Choose an organization…</option>
            {options.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </select>
        </Field>

        <Field
          label="Visibility"
          hint="Public means readable by everyone in the organization — never outside it."
        >
          <select className={inputClass} value={form.visibility} onChange={set('visibility')}>
            <option value="PRIVATE">Private — project members only</option>
            <option value="PUBLIC">Public — anyone in the organization</option>
          </select>
        </Field>

        <div className="flex justify-end gap-2 pt-1">
          <Button
            type="button"
            onClick={() => {
              reset()
              onClose()
            }}
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={!organization}
            loading={create.isPending}
          >
            Create project
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function suggestKey(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return ''
  if (words.length === 1) return words[0].slice(0, 4).toUpperCase()
  return words
    .map((word) => word[0])
    .join('')
    .slice(0, 4)
    .toUpperCase()
}

export function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden>
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  )
}

export function SearchIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" className={className} aria-hidden>
      <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
      <path d="m16.5 16.5 4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}
