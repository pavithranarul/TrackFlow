import { useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useTransitionIssue } from '../lib/queries'
import type { Issue, IssueStatus, IssueSummary } from '../lib/types'
import { STATUSES, STATUS_LABEL } from '../lib/types'
import { Avatar, cx, PriorityBadge, Skeleton, TypeIcon, useToast } from './ui'

/** Mirrors the backend's Issue.ALLOWED_TRANSITIONS so a column can be dimmed
 *  the moment a drag starts, before any request is made. The backend remains
 *  the authority — an illegal drop is still rejected there. */
const ALLOWED: Record<IssueStatus, IssueStatus[]> = {
  TODO: ['IN_PROGRESS'],
  IN_PROGRESS: ['TODO', 'TESTING'],
  TESTING: ['IN_PROGRESS', 'DONE'],
  DONE: ['IN_PROGRESS'],
}

const COLUMN_ACCENT: Record<IssueStatus, string> = {
  TODO: 'bg-slate-400',
  IN_PROGRESS: 'bg-amber-400',
  TESTING: 'bg-violet-400',
  DONE: 'bg-emerald-400',
}

interface BoardProps {
  issues: IssueSummary[]
  loading: boolean
  onOpen: (id: number) => void
  canWrite: boolean
}

export default function Board({ issues, loading, onOpen, canWrite }: BoardProps) {
  const [dragging, setDragging] = useState<IssueSummary | null>(null)
  const [over, setOver] = useState<IssueStatus | null>(null)
  const transition = useTransitionIssue()
  const queryClient = useQueryClient()
  const toast = useToast()

  const columns = useMemo(() => {
    const grouped: Record<IssueStatus, IssueSummary[]> = {
      TODO: [],
      IN_PROGRESS: [],
      TESTING: [],
      DONE: [],
    }
    for (const issue of issues) grouped[issue.status]?.push(issue)
    return grouped
  }, [issues])

  const canDropOn = (status: IssueStatus) =>
    !!dragging && (dragging.status === status || ALLOWED[dragging.status].includes(status))

  async function drop(status: IssueStatus) {
    const issue = dragging
    setDragging(null)
    setOver(null)

    if (!issue || issue.status === status) return

    if (!ALLOWED[issue.status].includes(status)) {
      toast(
        `${issue.key} cannot move from ${STATUS_LABEL[issue.status]} to ${STATUS_LABEL[status]}.`,
      )
      return
    }

    // Optimistic: move the card immediately, roll back if the server disagrees.
    const snapshot = queryClient.getQueriesData({ queryKey: ['issues'] })
    queryClient.setQueriesData({ queryKey: ['issues'] }, (old: unknown) => {
      const page = old as { results?: IssueSummary[] } | undefined
      if (!page?.results) return old
      return {
        ...page,
        results: page.results.map((row) =>
          row.id === issue.id ? { ...row, status } : row,
        ),
      }
    })

    try {
      await transition.mutateAsync({ id: issue.id, status })
    } catch (error) {
      for (const [key, value] of snapshot) queryClient.setQueryData(key, value)
      toast((error as Error).message)
    }
  }

  if (loading) {
    return (
      <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-4">
        {STATUSES.map((status) => (
          <div key={status} className="space-y-2">
            <Skeleton className="h-6 w-28" />
            {[0, 1, 2].map((n) => (
              <Skeleton key={n} className="h-[86px]" />
            ))}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-4">
      {STATUSES.map((status) => {
        const cards = columns[status]
        const droppable = canDropOn(status)
        const blocked = !!dragging && !droppable

        return (
          <section
            key={status}
            onDragOver={(event) => {
              if (!droppable) return
              event.preventDefault()
              setOver(status)
            }}
            onDragLeave={() => setOver((current) => (current === status ? null : current))}
            onDrop={(event) => {
              event.preventDefault()
              void drop(status)
            }}
            className={cx(
              'flex min-h-[180px] flex-col rounded-xl border p-2.5 transition-all duration-150',
              over === status && droppable
                ? 'border-[var(--color-accent)] bg-[var(--color-accent-soft)] ring-2 ring-[var(--color-accent)]/25'
                : 'border-[var(--color-line)] bg-[var(--color-surface)]',
              blocked && 'opacity-40',
            )}
          >
            <header className="mb-2.5 flex items-center gap-2 px-1">
              <span className={cx('h-2 w-2 rounded-full', COLUMN_ACCENT[status])} aria-hidden />
              <h3 className="text-[13px] font-semibold">{STATUS_LABEL[status]}</h3>
              <span className="ml-auto rounded-md bg-[var(--color-canvas)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--color-muted)] tabular-nums">
                {cards.length}
              </span>
            </header>

            <div className="flex flex-1 flex-col gap-2">
              {cards.map((issue) => (
                <Card
                  key={issue.id}
                  issue={issue}
                  draggable={canWrite}
                  isDragging={dragging?.id === issue.id}
                  onDragStart={() => setDragging(issue)}
                  onDragEnd={() => {
                    setDragging(null)
                    setOver(null)
                  }}
                  onOpen={() => onOpen(issue.id)}
                />
              ))}

              {cards.length === 0 && (
                <p
                  className={cx(
                    'flex flex-1 items-center justify-center rounded-lg border border-dashed border-[var(--color-line)] py-6 text-[12px] text-[var(--color-faint)]',
                    over === status && droppable && 'border-[var(--color-accent)]',
                  )}
                >
                  {dragging ? (droppable ? 'Drop here' : 'Not allowed') : 'Nothing here'}
                </p>
              )}
            </div>
          </section>
        )
      })}
    </div>
  )
}

function Card({
  issue,
  draggable,
  isDragging,
  onDragStart,
  onDragEnd,
  onOpen,
}: {
  issue: IssueSummary
  draggable: boolean
  isDragging: boolean
  onDragStart: () => void
  onDragEnd: () => void
  onOpen: () => void
}) {
  return (
    <article
      draggable={draggable}
      onDragStart={(event) => {
        event.dataTransfer.effectAllowed = 'move'
        // Firefox will not start a drag without data on the transfer.
        event.dataTransfer.setData('text/plain', String(issue.id))
        onDragStart()
      }}
      onDragEnd={onDragEnd}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen()
        }
      }}
      role="button"
      tabIndex={0}
      className={cx(
        'group rounded-lg border border-[var(--color-line)] bg-[var(--color-raised)] p-2.5 text-left shadow-sm transition-all',
        'hover:border-[var(--color-accent)]/50 hover:shadow-md',
        draggable ? 'cursor-grab active:cursor-grabbing' : 'cursor-pointer',
        isDragging && 'rotate-1 opacity-40',
      )}
    >
      <div className="mb-1.5 flex items-center gap-1.5">
        <TypeIcon type={issue.type} />
        <span className="font-mono text-[11px] font-medium text-[var(--color-faint)]">
          {issue.key}
        </span>
        <span className="ml-auto">
          <Avatar name={issue.assignee} size={20} />
        </span>
      </div>

      <p className="mb-2 line-clamp-2 text-[13px] leading-snug font-medium text-[var(--color-ink)]">
        {issue.title}
      </p>

      <PriorityBadge priority={issue.priority} />
    </article>
  )
}

/** Prefetch an issue on hover so opening the panel feels instant. */
export function prefetchIssue(queryClient: ReturnType<typeof useQueryClient>, id: number) {
  void queryClient.prefetchQuery({
    queryKey: ['issue', id],
    queryFn: () => api.get<Issue>(`/api/issues/${id}/`),
  })
}
