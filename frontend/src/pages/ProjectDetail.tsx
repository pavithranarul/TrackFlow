import { useMemo, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import {
  useCreateIssue,
  useIssues,
  useMembers,
  useProject,
} from '../lib/queries'
import { PRIORITIES, STATUSES, STATUS_LABEL, TYPES, type Role } from '../lib/types'
import Board from '../components/Board'
import IssuePanel from '../components/IssuePanel'
import IssueTable from '../components/IssueTable'
import Members from '../components/Members'
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
  useDebounced,
  useToast,
} from '../components/ui'
import { PlusIcon, SearchIcon } from './Projects'

type Tab = 'board' | 'list' | 'members'

/** Roles allowed to create and edit issues — mirrors issues.api.permissions. */
const WRITE_ROLES: Role[] = ['OWNER', 'MANAGER', 'DEVELOPER']

export default function ProjectDetail() {
  const { id } = useParams()
  const projectId = Number(id)
  const { user } = useAuth()

  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as Tab) ?? 'board'
  const openIssue = params.get('issue') ? Number(params.get('issue')) : null

  const [search, setSearch] = useState('')
  const [priority, setPriority] = useState<string[]>([])
  const [assignee, setAssignee] = useState('')
  const [creating, setCreating] = useState(false)

  const debounced = useDebounced(search)

  const { data: project, isLoading: loadingProject } = useProject(projectId)
  const { data: members } = useMembers(projectId)

  const { data: issues, isLoading: loadingIssues } = useIssues({
    projectId,
    search: debounced,
    priority,
    assignee_username: assignee,
    ordering: '-created_at',
  })

  const myRole = useMemo<Role | null>(() => {
    if (!project || !user) return null
    if (project.owner === user.username) return 'OWNER'
    const membership = members?.results.find((m) => m.username === user.username)
    return membership?.role ?? null
  }, [project, members, user])

  const canWrite = myRole !== null && WRITE_ROLES.includes(myRole)

  const setTab = (next: Tab) => {
    params.set('tab', next)
    setParams(params, { replace: true })
  }

  const setOpenIssue = (issueId: number | null) => {
    if (issueId === null) params.delete('issue')
    else params.set('issue', String(issueId))
    setParams(params, { replace: true })
  }

  if (loadingProject) {
    return (
      <div className="space-y-3 p-5">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (!project) {
    return (
      <div className="p-5">
        <EmptyState
          title="Project not found"
          hint="It may have been deleted, or you may no longer have access to it."
        />
      </div>
    )
  }

  const tabs: [Tab, string, number | undefined][] = [
    ['board', 'Board', undefined],
    ['list', 'Issues', issues?.count],
    ['members', 'Members', members?.count],
  ]

  return (
    <>
      <PageHeader
        title={
          <span className="flex items-center gap-2.5">
            <span className="rounded-md bg-[var(--color-accent-soft)] px-2 py-0.5 font-mono text-[12px] font-bold text-[var(--color-accent)]">
              {project.key}
            </span>
            {project.name}
          </span>
        }
        subtitle={project.description || `Owned by ${project.owner}`}
        actions={
          canWrite && (
            <Button variant="primary" onClick={() => setCreating(true)}>
              <PlusIcon /> New issue
            </Button>
          )
        }
      >
        <div className="flex items-center gap-1 border-t border-[var(--color-line)] px-5 pt-1">
          {tabs.map(([key, label, count]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={cx(
                '-mb-px border-b-2 px-2.5 py-2 text-[13px] font-medium transition-colors',
                tab === key
                  ? 'border-[var(--color-accent)] text-[var(--color-ink)]'
                  : 'border-transparent text-[var(--color-muted)] hover:text-[var(--color-ink)]',
              )}
            >
              {label}
              {count !== undefined && (
                <span className="ml-1.5 text-[var(--color-faint)] tabular-nums">{count}</span>
              )}
            </button>
          ))}

          {myRole && (
            <span className="ml-auto pb-1 text-[12px] text-[var(--color-faint)]">
              You are {myRole === 'OWNER' ? 'an' : 'a'} {myRole.toLowerCase()}
            </span>
          )}
        </div>

        {tab !== 'members' && (
          <div className="flex flex-wrap gap-2 border-t border-[var(--color-line)] px-5 py-2.5">
            <div className="relative min-w-[200px] flex-1 sm:max-w-xs">
              <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-[var(--color-faint)]" />
              <input
                className={cx(inputClass, 'py-1.5 pl-8 text-[13px]')}
                placeholder="Search issues…"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
            </div>

            <select
              className={filterClass}
              value={priority[0] ?? ''}
              onChange={(event) =>
                setPriority(event.target.value ? [event.target.value] : [])
              }
            >
              <option value="">Any priority</option>
              {PRIORITIES.map((value) => (
                <option key={value} value={value}>
                  {value[0] + value.slice(1).toLowerCase()}
                </option>
              ))}
            </select>

            <select
              className={filterClass}
              value={assignee}
              onChange={(event) => setAssignee(event.target.value)}
            >
              <option value="">Anyone</option>
              {user && <option value={user.username}>Assigned to me</option>}
              {members?.results
                .filter((member) => member.username !== user?.username)
                .map((member) => (
                  <option key={member.id} value={member.username}>
                    {member.username}
                  </option>
                ))}
            </select>

            {(priority.length > 0 || assignee || search) && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setPriority([])
                  setAssignee('')
                  setSearch('')
                }}
              >
                Clear
              </Button>
            )}
          </div>
        )}
      </PageHeader>

      {tab === 'board' && (
        <Board
          issues={issues?.results ?? []}
          loading={loadingIssues}
          onOpen={setOpenIssue}
          canWrite={canWrite}
        />
      )}

      {tab === 'list' && (
        <div className="p-5">
          <IssueTable
            issues={issues?.results ?? []}
            loading={loadingIssues}
            onOpen={setOpenIssue}
            showProject={false}
          />
        </div>
      )}

      {tab === 'members' && (
        <div className="p-5">
          <Members projectId={projectId} myRole={myRole} ownerUsername={project.owner} />
        </div>
      )}

      <IssuePanel
        issueId={openIssue}
        onClose={() => setOpenIssue(null)}
        canWrite={canWrite}
      />

      <CreateIssueModal
        projectId={projectId}
        open={creating}
        onClose={() => setCreating(false)}
      />
    </>
  )
}

function CreateIssueModal({
  projectId,
  open,
  onClose,
}: {
  projectId: number
  open: boolean
  onClose: () => void
}) {
  const create = useCreateIssue(projectId)
  const { data: members } = useMembers(projectId)
  const toast = useToast()

  const empty = {
    title: '',
    description: '',
    type: 'TASK',
    priority: 'MEDIUM',
    status: 'TODO',
    assignee: '',
  }
  const [form, setForm] = useState(empty)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((current) => ({ ...current, [key]: event.target.value }))

  return (
    <Modal
      open={open}
      onClose={() => {
        setForm(empty)
        setErrors({})
        onClose()
      }}
      title="New issue"
    >
      <form
        className="space-y-3.5"
        onSubmit={async (event) => {
          event.preventDefault()
          setErrors({})
          try {
            await create.mutateAsync({
              ...form,
              assignee: form.assignee ? Number(form.assignee) : null,
            })
            toast('Issue created.', 'success')
            setForm(empty)
            onClose()
          } catch (error) {
            if (error instanceof ApiError) setErrors(error.fields)
            else toast((error as Error).message)
          }
        }}
      >
        <Field label="Title" error={errors.title?.[0]}>
          <input className={inputClass} value={form.title} onChange={set('title')} autoFocus required />
        </Field>

        <Field label="Description" error={errors.description?.[0]}>
          <textarea
            className={cx(inputClass, 'min-h-24 resize-y')}
            value={form.description}
            onChange={set('description')}
          />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Type">
            <select className={inputClass} value={form.type} onChange={set('type')}>
              {TYPES.map((value) => (
                <option key={value} value={value}>
                  {value[0] + value.slice(1).toLowerCase()}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Priority">
            <select className={inputClass} value={form.priority} onChange={set('priority')}>
              {PRIORITIES.map((value) => (
                <option key={value} value={value}>
                  {value[0] + value.slice(1).toLowerCase()}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Status">
            <select className={inputClass} value={form.status} onChange={set('status')}>
              {STATUSES.map((value) => (
                <option key={value} value={value}>
                  {STATUS_LABEL[value]}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Assignee" error={errors.assignee?.[0]}>
            <select className={inputClass} value={form.assignee} onChange={set('assignee')}>
              <option value="">Unassigned</option>
              {members?.results.map((member) => (
                <option key={member.id} value={member.user}>
                  {member.username}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={create.isPending}>
            Create issue
          </Button>
        </div>
      </form>
    </Modal>
  )
}
