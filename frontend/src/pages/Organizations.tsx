import { useState } from 'react'
import { ApiError } from '../lib/api'
import { useAuth } from '../lib/auth'
import {
  useAddOrgMember,
  useCreateOrganization,
  useDeleteOrganization,
  useOrgMembers,
  useOrganization,
  useOrganizations,
  useRemoveOrgMember,
  useUpdateOrgMemberRole,
  useUsers,
} from '../lib/queries'
import { ORG_ROLES, type OrgRole, type Organization } from '../lib/types'
import { PageHeader } from '../components/Layout'
import {
  Avatar,
  Button,
  cx,
  EmptyState,
  Field,
  filterClass,
  inputClass,
  Modal,
  Skeleton,
  timeAgo,
  useToast,
} from '../components/ui'
import { PlusIcon } from './Projects'

export default function Organizations() {
  const { user } = useAuth()
  const { data, isLoading } = useOrganizations()
  const [creating, setCreating] = useState(false)
  const [openOrg, setOpenOrg] = useState<Organization | null>(null)

  const isSuperAdmin = Boolean(user?.is_superuser)

  return (
    <>
      <PageHeader
        title="Organizations"
        subtitle={
          isSuperAdmin
            ? 'Every organization on this installation'
            : 'The organizations you belong to'
        }
        actions={
          isSuperAdmin && (
            <Button variant="primary" onClick={() => setCreating(true)}>
              <PlusIcon /> New organization
            </Button>
          )
        }
      />

      <div className="p-5">
        {!isSuperAdmin && (
          <p className="mb-4 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] px-3.5 py-2.5 text-[12.5px] text-[var(--color-muted)]">
            Only a super admin can create an organization. If you are an admin of
            one, you can manage its members here.
          </p>
        )}

        {isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {[0, 1, 2].map((n) => (
              <Skeleton key={n} className="h-[132px]" />
            ))}
          </div>
        ) : data && data.results.length > 0 ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {data.results.map((org) => (
              <button
                key={org.id}
                onClick={() => setOpenOrg(org)}
                className="group rounded-xl border border-[var(--color-line)] bg-[var(--color-surface)] p-4 text-left transition-all hover:-translate-y-0.5 hover:border-[var(--color-accent)]/50 hover:shadow-md"
              >
                <div className="mb-2.5 flex items-center gap-2">
                  <span className="rounded-md bg-[var(--color-accent-soft)] px-1.5 py-0.5 font-mono text-[11px] font-bold text-[var(--color-accent)]">
                    {org.slug}
                  </span>
                  {org.my_role === 'ADMIN' && (
                    <span className="rounded-md bg-teal-500/15 px-1.5 py-0.5 text-[11px] font-medium text-teal-700 dark:text-teal-400">
                      Admin
                    </span>
                  )}
                  {!org.is_active && (
                    <span className="rounded-md bg-slate-500/12 px-1.5 py-0.5 text-[11px] font-medium text-[var(--color-muted)]">
                      Inactive
                    </span>
                  )}
                </div>

                <h3 className="truncate font-semibold tracking-tight group-hover:text-[var(--color-accent)]">
                  {org.name}
                </h3>

                <div className="mt-2.5 flex gap-4 text-[12px] text-[var(--color-muted)]">
                  <span>
                    <strong className="font-semibold text-[var(--color-ink)] tabular-nums">
                      {org.member_count}
                    </strong>{' '}
                    member{org.member_count === 1 ? '' : 's'}
                  </span>
                  <span>
                    <strong className="font-semibold text-[var(--color-ink)] tabular-nums">
                      {org.project_count}
                    </strong>{' '}
                    project{org.project_count === 1 ? '' : 's'}
                  </span>
                </div>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState
            title="No organizations"
            hint={
              isSuperAdmin
                ? 'Create one, then add people to it. Projects live inside organizations.'
                : 'Ask a super admin to add you to one.'
            }
            action={
              isSuperAdmin && (
                <Button variant="primary" onClick={() => setCreating(true)}>
                  <PlusIcon /> New organization
                </Button>
              )
            }
          />
        )}
      </div>

      <CreateOrgModal open={creating} onClose={() => setCreating(false)} />

      {openOrg && (
        <OrgMembersModal org={openOrg} onClose={() => setOpenOrg(null)} />
      )}
    </>
  )
}

function CreateOrgModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const create = useCreateOrganization()
  const { data: users } = useUsers('')
  const toast = useToast()

  const empty = { name: '', slug: '', description: '', admin: '' }
  const [form, setForm] = useState(empty)
  const [errors, setErrors] = useState<Record<string, string[]>>({})

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm((c) => ({ ...c, [key]: e.target.value }))

  const close = () => {
    setForm(empty)
    setErrors({})
    onClose()
  }

  return (
    <Modal open={open} onClose={close} title="New organization">
      <form
        className="space-y-3.5"
        onSubmit={async (event) => {
          event.preventDefault()
          setErrors({})
          try {
            await create.mutateAsync({
              name: form.name,
              slug: form.slug,
              description: form.description,
              admin: form.admin ? Number(form.admin) : null,
            })
            toast('Organization created.', 'success')
            close()
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
              setForm((c) => ({
                ...c,
                name,
                slug: c.slug === '' || c.slug === slugify(c.name) ? slugify(name) : c.slug,
              }))
            }}
            autoFocus
            required
          />
        </Field>

        <Field label="Slug" error={errors.slug?.[0]} hint="URL-safe and permanent.">
          <input
            className={cx(inputClass, 'font-mono')}
            value={form.slug}
            onChange={(event) => setForm((c) => ({ ...c, slug: slugify(event.target.value) }))}
            maxLength={50}
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
          label="First admin"
          error={errors.admin?.[0]}
          hint="They will run the organization day to day. Defaults to you."
        >
          <select className={inputClass} value={form.admin} onChange={set('admin')}>
            <option value="">Me</option>
            {users?.results.map((u) => (
              <option key={u.id} value={u.id}>
                {u.username}
              </option>
            ))}
          </select>
        </Field>

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={create.isPending}>
            Create organization
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function OrgMembersModal({ org, onClose }: { org: Organization; onClose: () => void }) {
  const { user } = useAuth()
  const { data: members } = useOrgMembers(org.id)
  const { data: users } = useUsers('')
  // The list serializer omits `description`, so read the detail shape rather
  // than showing "No description" for an organization that has one.
  const { data: detail } = useOrganization(org.id)
  const description = detail?.description ?? org.description

  const addMember = useAddOrgMember(org.id)
  const updateRole = useUpdateOrgMemberRole(org.id)
  const removeMember = useRemoveOrgMember(org.id)
  const deleteOrg = useDeleteOrganization()
  const toast = useToast()

  const [pick, setPick] = useState('')
  const [role, setRole] = useState<OrgRole>('MEMBER')

  const canManage = org.my_role === 'ADMIN'
  const isSuperAdmin = Boolean(user?.is_superuser)
  const adminCount = members?.results.filter((m) => m.role === 'ADMIN').length ?? 0
  const existing = new Set(members?.results.map((m) => m.user) ?? [])

  const run = async (action: Promise<unknown>) => {
    try {
      await action
    } catch (error) {
      toast((error as Error).message)
    }
  }

  return (
    <Modal open onClose={onClose} title={org.name} width="max-w-xl">
      <p className="mb-4 text-[12.5px] text-[var(--color-muted)]">
        {description || 'No description.'} Everything inside an organization is
        sealed off from every other one — a public project is public only to this
        organization's members.
      </p>

      {canManage && (
        <div className="mb-4 flex flex-wrap gap-2 rounded-lg border border-[var(--color-line)] bg-[var(--color-surface)] p-2.5">
          <select
            className={cx(filterClass, 'min-w-[160px] flex-1')}
            value={pick}
            onChange={(event) => setPick(event.target.value)}
          >
            <option value="">Add someone…</option>
            {users?.results
              .filter((u) => !existing.has(u.id))
              .map((u) => (
                <option key={u.id} value={u.id}>
                  {u.username}
                </option>
              ))}
          </select>

          <select
            className={filterClass}
            value={role}
            onChange={(event) => setRole(event.target.value as OrgRole)}
          >
            {ORG_ROLES.map((r) => (
              <option key={r} value={r}>
                {r[0] + r.slice(1).toLowerCase()}
              </option>
            ))}
          </select>

          <Button
            size="sm"
            variant="primary"
            disabled={!pick}
            loading={addMember.isPending}
            onClick={async () => {
              await run(
                addMember.mutateAsync({ user: Number(pick), role }).then(() => setPick('')),
              )
            }}
          >
            Add
          </Button>
        </div>
      )}

      <div className="max-h-72 overflow-y-auto rounded-lg border border-[var(--color-line)]">
        {members?.results.map((member) => {
          const isLastAdmin = member.role === 'ADMIN' && adminCount <= 1

          return (
            <div
              key={member.id}
              className="flex items-center gap-2.5 border-b border-[var(--color-line)] px-3 py-2.5 last:border-0"
            >
              <Avatar name={member.username} size={28} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-medium">{member.username}</p>
                <p className="text-[11px] text-[var(--color-faint)]">
                  Joined {timeAgo(member.joined_at)}
                </p>
              </div>

              {canManage && !isLastAdmin ? (
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
                  {ORG_ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r[0] + r.slice(1).toLowerCase()}
                    </option>
                  ))}
                </select>
              ) : (
                <span
                  title={isLastAdmin ? 'The last admin cannot be changed' : undefined}
                  className={cx(
                    'rounded-md px-2 py-0.5 text-[11px] font-semibold',
                    member.role === 'ADMIN'
                      ? 'bg-teal-500/15 text-teal-700 dark:text-teal-400'
                      : 'bg-slate-500/12 text-[var(--color-muted)]',
                  )}
                >
                  {member.role[0] + member.role.slice(1).toLowerCase()}
                </span>
              )}

              {canManage && !isLastAdmin && (
                <button
                  onClick={async () => {
                    if (!confirm(`Remove ${member.username} from ${org.name}?`)) return
                    await run(removeMember.mutateAsync(member.id))
                  }}
                  aria-label={`Remove ${member.username}`}
                  className="rounded-md p-1.5 text-[var(--color-faint)] transition-colors hover:bg-rose-500/10 hover:text-rose-500"
                >
                  <svg viewBox="0 0 24 24" width="15" height="15" fill="none" aria-hidden>
                    <path
                      d="M5 7h14M10 11v6m4-6v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                    />
                  </svg>
                </button>
              )}
            </div>
          )
        })}
      </div>

      {adminCount <= 1 && canManage && (
        <p className="mt-2.5 text-[12px] text-[var(--color-faint)]">
          Promote a second admin before changing or removing the current one.
        </p>
      )}

      {isSuperAdmin && (
        <div className="mt-5 flex items-center justify-between rounded-lg border border-rose-500/25 bg-rose-500/5 px-3.5 py-3">
          <p className="text-[12px] text-[var(--color-muted)]">
            Deleting removes {org.project_count} project
            {org.project_count === 1 ? '' : 's'} and everything in them.
          </p>
          <Button
            size="sm"
            variant="danger"
            onClick={async () => {
              if (!confirm(`Delete ${org.name} and all of its projects?`)) return
              await run(deleteOrg.mutateAsync(org.id).then(onClose))
            }}
          >
            Delete
          </Button>
        </div>
      )}
    </Modal>
  )
}

function slugify(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 50)
}
