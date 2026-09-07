import { Link } from 'react-router-dom'
import type { IssueSummary } from '../lib/types'
import { Avatar, EmptyState, PriorityBadge, Skeleton, StatusBadge, timeAgo, TypeIcon } from './ui'

export default function IssueTable({
  issues,
  loading,
  onOpen,
  showProject,
}: {
  issues: IssueSummary[]
  loading: boolean
  onOpen: (id: number) => void
  showProject: boolean
}) {
  if (loading) {
    return (
      <div className="space-y-1.5">
        {[0, 1, 2, 3, 4].map((n) => (
          <Skeleton key={n} className="h-11" />
        ))}
      </div>
    )
  }

  if (issues.length === 0) {
    return (
      <EmptyState
        title="No issues match"
        hint="Adjust the filters, or create the first issue for this project."
      />
    )
  }

  return (
    <div className="overflow-hidden rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)]">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-[var(--color-line)] text-[11px] font-semibold tracking-wider text-[var(--color-faint)] uppercase">
            <th className="px-3 py-2 font-semibold">Issue</th>
            <th className="hidden px-3 py-2 font-semibold sm:table-cell">Status</th>
            <th className="hidden px-3 py-2 font-semibold md:table-cell">Priority</th>
            <th className="hidden px-3 py-2 font-semibold lg:table-cell">Assignee</th>
            <th className="hidden px-3 py-2 text-right font-semibold lg:table-cell">Updated</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((issue) => (
            <tr
              key={issue.id}
              onClick={() => onOpen(issue.id)}
              className="cursor-pointer border-b border-[var(--color-line)] transition-colors last:border-0 hover:bg-[var(--color-canvas)]"
            >
              <td className="px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <TypeIcon type={issue.type} />
                  {showProject ? (
                    <Link
                      to={`/projects/${issue.project}`}
                      onClick={(event) => event.stopPropagation()}
                      className="shrink-0 rounded bg-[var(--color-accent-soft)] px-1.5 py-0.5 font-mono text-[10px] font-bold text-[var(--color-accent)] hover:underline"
                    >
                      {issue.project_key}
                    </Link>
                  ) : null}
                  <span className="shrink-0 font-mono text-[11px] text-[var(--color-faint)]">
                    {issue.key}
                  </span>
                  <span className="truncate text-[13px] font-medium">{issue.title}</span>
                </div>
              </td>
              <td className="hidden px-3 py-2.5 sm:table-cell">
                <StatusBadge status={issue.status} />
              </td>
              <td className="hidden px-3 py-2.5 md:table-cell">
                <PriorityBadge priority={issue.priority} />
              </td>
              <td className="hidden px-3 py-2.5 lg:table-cell">
                <span className="flex items-center gap-1.5 text-[12px] text-[var(--color-muted)]">
                  <Avatar name={issue.assignee} size={20} />
                  {issue.assignee ?? 'Unassigned'}
                </span>
              </td>
              <td className="hidden px-3 py-2.5 text-right text-[12px] whitespace-nowrap text-[var(--color-faint)] lg:table-cell">
                {timeAgo(issue.updated_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
