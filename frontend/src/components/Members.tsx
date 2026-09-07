import { useState } from 'react'
import { ApiError } from '../lib/api'
import {
  useAddMember,
  useMembers,
  useRemoveMember,
  useUpdateMemberRole,
  useUsers,
} from '../lib/queries'
import { ROLES, type Role } from '../lib/types'
import {
  Avatar,
  Button,
  cx,
  Field,
  filterClass,
  inputClass,
  Modal,
  RoleBadge,
  Skeleton,
  timeAgo,
  useToast,
} from './ui'
import { PlusIcon } from '../pages/Projects'

const MANAGE_ROLES: Role[] = ['OWNER', 'MANAGER']

export default function Members({
  projectId,
  myRole,
  ownerUsername,
}: {
  projectId: number
  myRole: Role | null
  ownerUsername: string
}) {
  const { data, isLoading } = useMembers(projectId)
  const updateRole = useUpdateMemberRole(projectId)
  const removeMember = useRemoveMember(projectId)
  const toast = useToast()
  const [adding, setAdding] = useState(false)

  const canManage = myRole !== null && MANAGE_ROLES.includes(myRole)
  const isOwner = myRole === 'OWNER'
  const ownerCount = data?.results.filter((m) => m.role === 'OWNER').length ?? 0

  const run = async (action: Promise<unknown>) => {
    try {
      await action
    } catch (error) {
      toast((error as Error).message)
    }
  }

  if (isLoading) {
    return (
      <div className="space-y-1.5">
        {[0, 1, 2].map((n) => (
          <Skeleton key={n} className="h-14" />
        ))}
      </div>
    )
  }

  return (
    <>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold">Members</h2>
          <p className="mt-0.5 text-[12px] text-[var(--color-muted)]">
            Viewers are read-only. Developers can work on issues. Managers can also
            change membership. Only an owner can grant or revoke the owner role.
          </p>
        </div>
        {canManage && (
          <Button variant="primary" size="sm" onClick={() => setAdding(true)}>
            <PlusIcon /> Add member
          </Button>
        )}
      </div>

      <div className="overflow-hidden rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)]">
        {data?.results.map((member) => {
          // The backend refuses to demote or remove the last owner; disabling
          // the controls here explains why before the request is made.
          const isLastOwner = member.role === 'OWNER' && ownerCount <= 1
          const touchesOwner = member.role === 'OWNER'
          const mayEdit = canManage && (isOwner || !touchesOwner) && !isLastOwner

          return (
            <div
              key={member.id}
              className="flex flex-wrap items-center gap-3 border-b border-[var(--color-line)] px-3.5 py-3 last:border-0"
            >
              <Avatar name={member.username} size={32} />

              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium">
                  {member.username}
                  {member.username === ownerUsername && (
                    <span className="ml-1.5 text-[11px] text-[var(--color-faint)]">
                      · project creator
                    </span>
                  )}
                </p>
                <p className="text-[11px] text-[var(--color-faint)]">
                  Joined {timeAgo(member.joined_at)}
                </p>
              </div>

              {mayEdit ? (
                <select
                  className={filterClass}
                  value={member.role}
                  onChange={(event) =>
                    run(
                      updateRole.mutateAsync({
                        memberId: member.id,
                        role: event.target.value,
                      }),
                    )
                  }
                >
                  {ROLES.filter((role) => role !== 'OWNER' || isOwner).map((role) => (
                    <option key={role} value={role}>
                      {role[0] + role.slice(1).toLowerCase()}
                    </option>
                  ))}
                </select>
              ) : (
                <span title={isLastOwner ? 'The last owner cannot be changed' : undefined}>
                  <RoleBadge role={member.role} />
                </span>
              )}

              {mayEdit && (
                <button
                  onClick={async () => {
                    if (!confirm(`Remove ${member.username} from this project?`)) return
                    await run(removeMember.mutateAsync(member.id))
                  }}
                  className="rounded-md p-1.5 text-[var(--color-faint)] transition-colors hover:bg-rose-500/10 hover:text-rose-500"
                  aria-label={`Remove ${member.username}`}
                >
                  <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden>
                    <path
                      d="M5 7h14M10 11v6m4-6v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
              )}
            </div>
          )
        })}
      </div>

      {ownerCount <= 1 && canManage && (
        <p className="mt-2.5 text-[12px] text-[var(--color-faint)]">
          To hand over this project, promote someone else to owner first — the last
          owner cannot be demoted or removed.
        </p>
      )}

      <AddMemberModal
        projectId={projectId}
        open={adding}
        onClose={() => setAdding(false)}
        canGrantOwner={isOwner}
        existing={new Set(data?.results.map((m) => m.user) ?? [])}
      />
    </>
  )
}

function AddMemberModal({
  projectId,
  open,
  onClose,
  canGrantOwner,
  existing,
}: {
  projectId: number
  open: boolean
  onClose: () => void
  canGrantOwner: boolean
  existing: Set<number>
}) {
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<number | null>(null)
  const [role, setRole] = useState<Role>('DEVELOPER')
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  const { data: users } = useUsers(search)
  const add = useAddMember(projectId)
  const toast = useToast()

  const candidates = users?.results.filter((user) => !existing.has(user.id)) ?? []

  return (
    <Modal
      open={open}
      onClose={() => {
        setSelected(null)
        setSearch('')
        setErrors({})
        onClose()
      }}
      title="Add member"
    >
      <form
        className="space-y-3.5"
        onSubmit={async (event) => {
          event.preventDefault()
          if (selected === null) return
          setErrors({})
          try {
            await add.mutateAsync({ user: selected, role })
            toast('Member added.', 'success')
            setSelected(null)
            setSearch('')
            onClose()
          } catch (error) {
            if (error instanceof ApiError) setErrors(error.fields)
            else toast((error as Error).message)
          }
        }}
      >
        <Field label="Search people" error={errors.user?.[0]}>
          <input
            className={inputClass}
            placeholder="Username or name…"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            autoFocus
          />
        </Field>

        <div className="max-h-52 overflow-y-auto rounded-lg border border-[var(--color-line)]">
          {candidates.length === 0 && (
            <p className="px-3 py-6 text-center text-[13px] text-[var(--color-faint)]">
              {search ? 'Nobody matches that search.' : 'Everyone is already a member.'}
            </p>
          )}
          {candidates.map((user) => (
            <button
              key={user.id}
              type="button"
              onClick={() => setSelected(user.id)}
              className={cx(
                'flex w-full items-center gap-2.5 border-b border-[var(--color-line)] px-3 py-2 text-left transition-colors last:border-0',
                selected === user.id
                  ? 'bg-[var(--color-accent-soft)]'
                  : 'hover:bg-[var(--color-canvas)]',
              )}
            >
              <Avatar name={user.username} size={26} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-medium">{user.username}</span>
                {(user.first_name || user.last_name) && (
                  <span className="block truncate text-[11px] text-[var(--color-faint)]">
                    {user.first_name} {user.last_name}
                  </span>
                )}
              </span>
              {selected === user.id && (
                <span className="text-[var(--color-accent)]" aria-hidden>
                  ✓
                </span>
              )}
            </button>
          ))}
        </div>

        <Field label="Role" error={errors.role?.[0]}>
          <select
            className={inputClass}
            value={role}
            onChange={(event) => setRole(event.target.value as Role)}
          >
            {ROLES.filter((value) => value !== 'OWNER' || canGrantOwner).map((value) => (
              <option key={value} value={value}>
                {value[0] + value.slice(1).toLowerCase()}
              </option>
            ))}
          </select>
        </Field>

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="primary"
            disabled={selected === null}
            loading={add.isPending}
          >
            Add member
          </Button>
        </div>
      </form>
    </Modal>
  )
}
