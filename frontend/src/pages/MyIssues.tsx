import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../lib/auth'
import { useIssues } from '../lib/queries'
import { PRIORITIES, STATUSES, STATUS_LABEL } from '../lib/types'
import IssueTable from '../components/IssueTable'
import IssuePanel from '../components/IssuePanel'
import { PageHeader } from '../components/Layout'
import { Button, cx, filterClass, inputClass, useDebounced } from '../components/ui'
import { SearchIcon } from './Projects'

type Scope = 'assigned' | 'reported' | 'all'

export default function MyIssues() {
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const openIssue = params.get('issue') ? Number(params.get('issue')) : null

  const [scope, setScope] = useState<Scope>('assigned')
  const [statuses, setStatuses] = useState<string[]>(['TODO', 'IN_PROGRESS', 'TESTING'])
  const [priority, setPriority] = useState('')
  const [search, setSearch] = useState('')

  const debounced = useDebounced(search)

  const { data, isLoading } = useIssues({
    search: debounced,
    status: statuses,
    priority: priority ? [priority] : [],
    assignee_username: scope === 'assigned' ? user?.username : undefined,
    ...(scope === 'reported' ? { reporter_username: user?.username } : {}),
    ordering: '-updated_at',
  })

  const setOpenIssue = (id: number | null) => {
    if (id === null) params.delete('issue')
    else params.set('issue', String(id))
    setParams(params, { replace: true })
  }

  const toggleStatus = (status: string) =>
    setStatuses((current) =>
      current.includes(status)
        ? current.filter((value) => value !== status)
        : [...current, status],
    )

  return (
    <>
      <PageHeader
        title="My issues"
        subtitle={
          data
            ? `${data.count} issue${data.count === 1 ? '' : 's'} across every project you can see`
            : undefined
        }
      >
        <div className="flex flex-wrap items-center gap-2 px-5 pb-3">
          <div className="flex rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] p-0.5">
            {(
              [
                ['assigned', 'Assigned to me'],
                ['reported', 'Reported by me'],
                ['all', 'Everything'],
              ] as [Scope, string][]
            ).map(([value, label]) => (
              <button
                key={value}
                onClick={() => setScope(value)}
                className={cx(
                  'rounded-md px-2.5 py-1 text-[12px] font-medium transition-colors',
                  scope === value
                    ? 'bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
                    : 'text-[var(--color-muted)] hover:text-[var(--color-ink)]',
                )}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="flex gap-1">
            {STATUSES.map((status) => (
              <button
                key={status}
                onClick={() => toggleStatus(status)}
                className={cx(
                  'rounded-md border px-2 py-1 text-[12px] font-medium transition-colors',
                  statuses.includes(status)
                    ? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent)]'
                    : 'border-[var(--color-line)] text-[var(--color-muted)] hover:text-[var(--color-ink)]',
                )}
              >
                {STATUS_LABEL[status]}
              </button>
            ))}
          </div>

          <select
            className={filterClass}
            value={priority}
            onChange={(event) => setPriority(event.target.value)}
          >
            <option value="">Any priority</option>
            {PRIORITIES.map((value) => (
              <option key={value} value={value}>
                {value[0] + value.slice(1).toLowerCase()}
              </option>
            ))}
          </select>

          <div className="relative min-w-[180px] flex-1 sm:max-w-xs">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-[var(--color-faint)]" />
            <input
              className={cx(inputClass, 'py-1.5 pl-8 text-[13px]')}
              placeholder="Search…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>

          {(search || priority || statuses.length !== 3) && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setSearch('')
                setPriority('')
                setStatuses(['TODO', 'IN_PROGRESS', 'TESTING'])
              }}
            >
              Reset
            </Button>
          )}
        </div>
      </PageHeader>

      <div className="p-5">
        <IssueTable
          issues={data?.results ?? []}
          loading={isLoading}
          onOpen={setOpenIssue}
          showProject
        />
      </div>

      <IssuePanel issueId={openIssue} onClose={() => setOpenIssue(null)} canWrite />
    </>
  )
}
