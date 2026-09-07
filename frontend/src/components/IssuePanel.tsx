import { useEffect, useState } from 'react'
import {
  useAddComment,
  useAssignIssue,
  useDeleteComment,
  useDeleteIssue,
  useIssue,
  useMembers,
  useTransitionIssue,
  useUpdateIssue,
} from '../lib/queries'
import { PRIORITIES, STATUS_LABEL, TYPES, type Activity } from '../lib/types'
import { useAuth } from '../lib/auth'
import {
  Avatar,
  Button,
  cx,
  inputClass,
  PriorityBadge,
  Skeleton,
  StatusBadge,
  timeAgo,
  TypeIcon,
  useToast,
} from './ui'

export default function IssuePanel({
  issueId,
  onClose,
  canWrite,
}: {
  issueId: number | null
  onClose: () => void
  canWrite: boolean
}) {
  const { data: issue, isLoading } = useIssue(issueId)
  const { user } = useAuth()
  const toast = useToast()

  const transition = useTransitionIssue()
  const assign = useAssignIssue()
  const update = useUpdateIssue()
  const remove = useDeleteIssue()
  const addComment = useAddComment(issueId ?? -1)
  const deleteComment = useDeleteComment(issueId ?? -1)

  const { data: members } = useMembers(issue?.project ?? NaN)

  const [comment, setComment] = useState('')
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({ title: '', description: '' })

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    setComment('')
    setEditing(false)
  }, [issueId])

  if (issueId === null) return null

  const run = async (action: Promise<unknown>) => {
    try {
      await action
    } catch (error) {
      toast((error as Error).message)
    }
  }

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]" onClick={onClose} aria-hidden />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label={issue ? `${issue.key} ${issue.title}` : 'Issue'}
        className="animate-slide-in fixed inset-y-0 right-0 z-50 flex w-full max-w-2xl flex-col border-l border-[var(--color-line)] bg-[var(--color-canvas)] shadow-2xl"
      >
        {/* Header */}
        <header className="flex items-center gap-2.5 border-b border-[var(--color-line)] px-5 py-3.5">
          {issue && (
            <>
              <TypeIcon type={issue.type} />
              <span className="font-mono text-[13px] font-medium text-[var(--color-muted)]">
                {issue.key}
              </span>
              <StatusBadge status={issue.status} />
            </>
          )}
          <div className="ml-auto flex items-center gap-1.5">
            {issue && canWrite && (
              <Button
                size="sm"
                variant="ghost"
                className="text-rose-500 hover:bg-rose-500/10"
                onClick={async () => {
                  if (!confirm(`Delete ${issue.key}? This cannot be undone.`)) return
                  await run(remove.mutateAsync(issue.id).then(onClose))
                }}
              >
                Delete
              </Button>
            )}
            <button
              onClick={onClose}
              aria-label="Close"
              className="rounded-md p-1.5 text-[var(--color-faint)] transition-colors hover:bg-[var(--color-surface)] hover:text-[var(--color-ink)]"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" aria-hidden>
                <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </button>
          </div>
        </header>

        {isLoading || !issue ? (
          <div className="space-y-3 p-5">
            <Skeleton className="h-7 w-2/3" />
            <Skeleton className="h-20" />
            <Skeleton className="h-32" />
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="grid gap-5 p-5 lg:grid-cols-[1fr_200px]">
              {/* Main column */}
              <div className="min-w-0">
                {editing ? (
                  <div className="space-y-2.5">
                    <input
                      className={cx(inputClass, 'text-base font-semibold')}
                      value={draft.title}
                      onChange={(e) => setDraft({ ...draft, title: e.target.value })}
                    />
                    <textarea
                      className={cx(inputClass, 'min-h-32 resize-y')}
                      value={draft.description}
                      placeholder="Add a description…"
                      onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="primary"
                        loading={update.isPending}
                        onClick={async () => {
                          await run(
                            update
                              .mutateAsync({ id: issue.id, body: draft })
                              .then(() => setEditing(false)),
                          )
                        }}
                      >
                        Save
                      </Button>
                      <Button size="sm" onClick={() => setEditing(false)}>
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="group">
                    <div className="flex items-start gap-2">
                      <h2 className="flex-1 text-[19px] leading-snug font-semibold tracking-tight">
                        {issue.title}
                      </h2>
                      {canWrite && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="opacity-0 transition-opacity group-hover:opacity-100"
                          onClick={() => {
                            setDraft({ title: issue.title, description: issue.description })
                            setEditing(true)
                          }}
                        >
                          Edit
                        </Button>
                      )}
                    </div>
                    <p className="mt-2.5 text-[14px] leading-relaxed whitespace-pre-wrap text-[var(--color-muted)]">
                      {issue.description || <span className="italic">No description.</span>}
                    </p>
                  </div>
                )}

                {/* Transitions */}
                {canWrite && issue.allowed_transitions.length > 0 && (
                  <div className="mt-5 flex flex-wrap items-center gap-2 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] p-2.5">
                    <span className="text-[12px] font-medium text-[var(--color-muted)]">
                      Move to
                    </span>
                    {issue.allowed_transitions.map((status) => (
                      <Button
                        key={status}
                        size="sm"
                        variant={status === 'DONE' ? 'primary' : 'secondary'}
                        loading={transition.isPending}
                        onClick={() =>
                          run(transition.mutateAsync({ id: issue.id, status }))
                        }
                      >
                        {STATUS_LABEL[status]}
                      </Button>
                    ))}
                  </div>
                )}

                {/* Comments */}
                <section className="mt-7">
                  <h3 className="mb-3 text-[13px] font-semibold">
                    Comments{' '}
                    <span className="font-normal text-[var(--color-faint)]">
                      {issue.comments.length}
                    </span>
                  </h3>

                  <div className="space-y-3">
                    {issue.comments.map((entry) => (
                      <article key={entry.id} className="group flex gap-2.5">
                        <Avatar name={entry.author?.username ?? null} size={26} />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-baseline gap-2">
                            <span className="text-[13px] font-medium">
                              {entry.author?.username ?? 'Deleted user'}
                            </span>
                            <span className="text-[11px] text-[var(--color-faint)]">
                              {timeAgo(entry.created_at)}
                            </span>
                            {entry.author?.id === user?.id && (
                              <button
                                onClick={() => run(deleteComment.mutateAsync(entry.id))}
                                className="ml-auto text-[11px] text-[var(--color-faint)] opacity-0 transition-opacity group-hover:opacity-100 hover:text-rose-500"
                              >
                                Delete
                              </button>
                            )}
                          </div>
                          <p className="mt-1 rounded-lg rounded-tl-none border border-[var(--color-line)] bg-[var(--color-surface)] px-3 py-2 text-[13px] leading-relaxed whitespace-pre-wrap">
                            {entry.body}
                          </p>
                        </div>
                      </article>
                    ))}

                    {issue.comments.length === 0 && (
                      <p className="text-[13px] text-[var(--color-faint)]">
                        No comments yet.
                      </p>
                    )}
                  </div>

                  {canWrite && (
                    <form
                      className="mt-3 flex gap-2.5"
                      onSubmit={async (event) => {
                        event.preventDefault()
                        if (!comment.trim()) return
                        await run(addComment.mutateAsync(comment).then(() => setComment('')))
                      }}
                    >
                      <Avatar name={user?.username} size={26} />
                      <div className="flex-1">
                        <textarea
                          className={cx(inputClass, 'min-h-[64px] resize-y')}
                          placeholder="Leave a comment…"
                          value={comment}
                          onChange={(event) => setComment(event.target.value)}
                          onKeyDown={(event) => {
                            if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                              event.currentTarget.form?.requestSubmit()
                            }
                          }}
                        />
                        <div className="mt-1.5 flex items-center gap-2">
                          <Button
                            type="submit"
                            size="sm"
                            variant="primary"
                            disabled={!comment.trim()}
                            loading={addComment.isPending}
                          >
                            Comment
                          </Button>
                          <span className="text-[11px] text-[var(--color-faint)]">⌘↵ to send</span>
                        </div>
                      </div>
                    </form>
                  )}
                </section>

                {/* Activity */}
                <section className="mt-7">
                  <h3 className="mb-3 text-[13px] font-semibold">Activity</h3>
                  <ol className="space-y-0">
                    {issue.activities.map((entry, index) => (
                      <ActivityRow
                        key={entry.id}
                        entry={entry}
                        last={index === issue.activities.length - 1}
                      />
                    ))}
                  </ol>
                </section>
              </div>

              {/* Sidebar */}
              <div className="space-y-4 lg:border-l lg:border-[var(--color-line)] lg:pl-5">
                <Meta label="Assignee">
                  {canWrite ? (
                    <select
                      className={cx(inputClass, 'py-1.5 text-[13px]')}
                      value={issue.assignee?.id ?? ''}
                      onChange={(event) =>
                        run(
                          assign.mutateAsync({
                            id: issue.id,
                            assignee: event.target.value ? Number(event.target.value) : null,
                          }),
                        )
                      }
                    >
                      <option value="">Unassigned</option>
                      {members?.results.map((member) => (
                        <option key={member.id} value={member.user}>
                          {member.username}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="flex items-center gap-1.5 text-[13px]">
                      <Avatar name={issue.assignee?.username ?? null} size={20} />
                      {issue.assignee?.username ?? 'Unassigned'}
                    </span>
                  )}
                </Meta>

                <Meta label="Priority">
                  {canWrite ? (
                    <select
                      className={cx(inputClass, 'py-1.5 text-[13px]')}
                      value={issue.priority}
                      onChange={(event) =>
                        run(
                          update.mutateAsync({
                            id: issue.id,
                            body: { priority: event.target.value },
                          }),
                        )
                      }
                    >
                      {PRIORITIES.map((priority) => (
                        <option key={priority} value={priority}>
                          {priority[0] + priority.slice(1).toLowerCase()}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <PriorityBadge priority={issue.priority} />
                  )}
                </Meta>

                <Meta label="Type">
                  {canWrite ? (
                    <select
                      className={cx(inputClass, 'py-1.5 text-[13px]')}
                      value={issue.type}
                      onChange={(event) =>
                        run(
                          update.mutateAsync({
                            id: issue.id,
                            body: { type: event.target.value },
                          }),
                        )
                      }
                    >
                      {TYPES.map((type) => (
                        <option key={type} value={type}>
                          {type[0] + type.slice(1).toLowerCase()}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="flex items-center gap-1.5 text-[13px]">
                      <TypeIcon type={issue.type} /> {issue.type.toLowerCase()}
                    </span>
                  )}
                </Meta>

                <Meta label="Reporter">
                  <span className="flex items-center gap-1.5 text-[13px]">
                    <Avatar name={issue.reporter?.username ?? null} size={20} />
                    {issue.reporter?.username ?? 'Deleted user'}
                  </span>
                </Meta>

                <Meta label="Created">
                  <span className="text-[13px] text-[var(--color-muted)]">
                    {timeAgo(issue.created_at)}
                  </span>
                </Meta>

                {issue.closed_at && (
                  <Meta label="Closed">
                    <span className="text-[13px] text-emerald-600 dark:text-emerald-400">
                      {timeAgo(issue.closed_at)}
                    </span>
                  </Meta>
                )}
              </div>
            </div>
          </div>
        )}
      </aside>
    </>
  )
}

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-1.5 text-[11px] font-semibold tracking-wider text-[var(--color-faint)] uppercase">
        {label}
      </p>
      {children}
    </div>
  )
}

const ACTION_DOT: Record<Activity['action'], string> = {
  CREATED: 'bg-[var(--color-accent)]',
  STATUS_CHANGED: 'bg-amber-400',
  ASSIGNED: 'bg-sky-400',
  UNASSIGNED: 'bg-slate-400',
  PRIORITY_CHANGED: 'bg-orange-400',
  UPDATED: 'bg-slate-400',
  COMMENTED: 'bg-violet-400',
}

function describe(entry: Activity): React.ReactNode {
  const strong = (text: string) => (
    <span className="font-medium text-[var(--color-ink)]">{text}</span>
  )

  switch (entry.action) {
    case 'CREATED':
      return <>created this issue</>
    case 'STATUS_CHANGED':
      return (
        <>
          moved it from {strong(entry.old_value)} to {strong(entry.new_value)}
        </>
      )
    case 'ASSIGNED':
      return <>assigned it to {strong(entry.new_value)}</>
    case 'UNASSIGNED':
      return <>unassigned {strong(entry.old_value)}</>
    case 'PRIORITY_CHANGED':
      return (
        <>
          changed priority from {strong(entry.old_value)} to {strong(entry.new_value)}
        </>
      )
    case 'COMMENTED':
      return <>commented</>
    default:
      return (
        <>
          changed {strong(entry.field || 'the issue')}
          {entry.new_value && <> to {strong(entry.new_value)}</>}
        </>
      )
  }
}

function ActivityRow({ entry, last }: { entry: Activity; last: boolean }) {
  return (
    <li className="relative flex gap-3 pb-3.5">
      {!last && (
        <span
          className="absolute top-4 bottom-0 left-[3.5px] w-px bg-[var(--color-line)]"
          aria-hidden
        />
      )}
      <span
        className={cx('mt-[6px] h-2 w-2 shrink-0 rounded-full', ACTION_DOT[entry.action])}
        aria-hidden
      />
      <p className="text-[12.5px] leading-relaxed text-[var(--color-muted)]">
        <span className="font-medium text-[var(--color-ink)]">
          {entry.actor ?? 'Someone'}
        </span>{' '}
        {describe(entry)}
        <span className="ml-1.5 text-[var(--color-faint)]">{timeAgo(entry.created_at)}</span>
      </p>
    </li>
  )
}
