import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
} from '@tanstack/react-query'
import { api, qs } from './api'
import type {
  Comment,
  Issue,
  IssueSummary,
  Member,
  OrgMember,
  Organization,
  Page,
  Project,
  User,
} from './types'

/* ------------------------------------------------------------------ keys */

export const keys = {
  me: ['me'] as const,
  users: (search: string) => ['users', search] as const,
  projects: (params: unknown) => ['projects', params] as const,
  project: (id: number) => ['project', id] as const,
  members: (projectId: number) => ['members', projectId] as const,
  issues: (params: unknown) => ['issues', params] as const,
  organizations: (params: unknown) => ['organizations', params] as const,
  organization: (id: number) => ['organization', id] as const,
  orgMembers: (id: number) => ['orgMembers', id] as const,
  issue: (id: number) => ['issue', id] as const,
}

/* ---------------------------------------------------------------- account */

export const useMe = (enabled: boolean) =>
  useQuery({
    queryKey: keys.me,
    queryFn: () => api.get<User>('/api/auth/me/'),
    enabled,
    staleTime: 5 * 60_000,
    retry: false,
  })

export const useUsers = (search = '') =>
  useQuery({
    queryKey: keys.users(search),
    queryFn: () => api.get<Page<User>>(`/api/auth/users/${qs({ search })}`),
    staleTime: 60_000,
  })

/* --------------------------------------------------------------- projects */

export interface ProjectQuery {
  search?: string
  status?: string
  visibility?: string
  ordering?: string
}

export const useProjects = (params: ProjectQuery = {}) =>
  useQuery({
    queryKey: keys.projects(params),
    queryFn: () => api.get<Page<Project>>(`/api/projects/${qs({ ...params })}`),
  })

export const useProject = (id: number) =>
  useQuery({
    queryKey: keys.project(id),
    queryFn: () => api.get<Project>(`/api/projects/${id}/`),
    enabled: Number.isFinite(id),
  })

/* ----------------------------------------------------------------- issues */

export interface IssueQuery {
  projectId?: number
  search?: string
  status?: string[]
  priority?: string[]
  type?: string[]
  assignee_username?: string
  unassigned?: string
  ordering?: string
  page?: number
}

function issuePath({ projectId, ...rest }: IssueQuery) {
  const base = projectId ? `/api/projects/${projectId}/issues/` : '/api/issues/'
  return `${base}${qs(rest as Record<string, unknown>)}`
}

export const useIssues = (params: IssueQuery) =>
  useQuery({
    queryKey: keys.issues(params),
    queryFn: () => api.get<Page<IssueSummary>>(issuePath(params)),
    // Keeps the board from flashing empty while a filter change refetches.
    placeholderData: (previous) => previous,
  })

export const useIssue = (id: number | null) =>
  useQuery({
    queryKey: keys.issue(id ?? -1),
    queryFn: () => api.get<Issue>(`/api/issues/${id}/`),
    enabled: id !== null,
  })

/* -------------------------------------------------------------- mutations */

/** Wraps useMutation so every write invalidates the lists it could affect.
 *  Without this a transition would update the panel but leave the board stale. */
function useInvalidatingMutation<TData, TVariables>(
  mutationFn: (variables: TVariables) => Promise<TData>,
  invalidate: (queryClient: ReturnType<typeof useQueryClient>, data: TData, variables: TVariables) => void,
  options?: Omit<UseMutationOptions<TData, Error, TVariables>, 'mutationFn'>,
) {
  const queryClient = useQueryClient()

  return useMutation<TData, Error, TVariables>({
    mutationFn,
    ...options,
    // Forwarded with a rest spread rather than named parameters: React Query
    // has changed this callback's arity between minor versions.
    onSuccess: (...args) => {
      const [data, variables] = args
      invalidate(queryClient, data, variables)
      options?.onSuccess?.(...args)
    },
  })
}

const invalidateIssueViews = (
  queryClient: ReturnType<typeof useQueryClient>,
  issue: Issue,
) => {
  queryClient.setQueryData(keys.issue(issue.id), issue)
  queryClient.invalidateQueries({ queryKey: ['issues'] })
}

export const useCreateProject = () =>
  useInvalidatingMutation(
    (body: Record<string, unknown>) => api.post<Project>('/api/projects/', body),
    (queryClient) => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  )

export const useUpdateProject = (id: number) =>
  useInvalidatingMutation(
    (body: Record<string, unknown>) => api.patch<Project>(`/api/projects/${id}/`, body),
    (queryClient) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      queryClient.invalidateQueries({ queryKey: keys.project(id) })
    },
  )

export const useDeleteProject = () =>
  useInvalidatingMutation(
    (id: number) => api.delete(`/api/projects/${id}/`),
    (queryClient) => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  )

export const useCreateIssue = (projectId: number) =>
  useInvalidatingMutation(
    (body: Record<string, unknown>) =>
      api.post<Issue>(`/api/projects/${projectId}/issues/`, body),
    (queryClient) => queryClient.invalidateQueries({ queryKey: ['issues'] }),
  )

export const useUpdateIssue = () =>
  useInvalidatingMutation(
    ({ id, body }: { id: number; body: Record<string, unknown> }) =>
      api.patch<Issue>(`/api/issues/${id}/`, body),
    invalidateIssueViews,
  )

export const useTransitionIssue = () =>
  useInvalidatingMutation(
    ({ id, status }: { id: number; status: string }) =>
      api.post<Issue>(`/api/issues/${id}/transition/`, { status }),
    invalidateIssueViews,
  )

export const useAssignIssue = () =>
  useInvalidatingMutation(
    ({ id, assignee }: { id: number; assignee: number | null }) =>
      api.post<Issue>(`/api/issues/${id}/assign/`, { assignee }),
    invalidateIssueViews,
  )

export const useDeleteIssue = () =>
  useInvalidatingMutation(
    (id: number) => api.delete(`/api/issues/${id}/`),
    (queryClient) => queryClient.invalidateQueries({ queryKey: ['issues'] }),
  )

export const useAddComment = (issueId: number) =>
  useInvalidatingMutation(
    (body: string) => api.post<Comment>(`/api/issues/${issueId}/comments/`, { body }),
    (queryClient) => queryClient.invalidateQueries({ queryKey: keys.issue(issueId) }),
  )

export const useDeleteComment = (issueId: number) =>
  useInvalidatingMutation(
    (commentId: number) => api.delete(`/api/comments/${commentId}/`),
    (queryClient) => queryClient.invalidateQueries({ queryKey: keys.issue(issueId) }),
  )

/* ----------------------------------------------------------- memberships */

export const useMembers = (projectId: number) =>
  useQuery({
    queryKey: keys.members(projectId),
    queryFn: () => api.get<Page<Member>>(`/api/projects/${projectId}/members/`),
    enabled: Number.isFinite(projectId),
  })

const invalidateMembers = (projectId: number) =>
  (queryClient: ReturnType<typeof useQueryClient>) => {
    queryClient.invalidateQueries({ queryKey: keys.members(projectId) })
    queryClient.invalidateQueries({ queryKey: keys.project(projectId) })
  }

export const useAddMember = (projectId: number) =>
  useInvalidatingMutation(
    (body: { user: number; role: string }) =>
      api.post<Member>(`/api/projects/${projectId}/members/`, body),
    invalidateMembers(projectId),
  )

export const useUpdateMemberRole = (projectId: number) =>
  useInvalidatingMutation(
    ({ memberId, role }: { memberId: number; role: string }) =>
      api.patch<Member>(`/api/projects/${projectId}/members/${memberId}/`, { role }),
    invalidateMembers(projectId),
  )

export const useRemoveMember = (projectId: number) =>
  useInvalidatingMutation(
    (memberId: number) => api.delete(`/api/projects/${projectId}/members/${memberId}/`),
    invalidateMembers(projectId),
  )


/* --------------------------------------------------------- organizations */

export const useOrganizations = (params: { search?: string } = {}) =>
  useQuery({
    queryKey: keys.organizations(params),
    queryFn: () => api.get<Page<Organization>>(`/api/organizations/${qs(params)}`),
  })

export const useOrganization = (id: number) =>
  useQuery({
    queryKey: keys.organization(id),
    queryFn: () => api.get<Organization>(`/api/organizations/${id}/`),
    enabled: Number.isFinite(id),
  })

export const useOrgMembers = (id: number) =>
  useQuery({
    queryKey: keys.orgMembers(id),
    queryFn: () => api.get<Page<OrgMember>>(`/api/organizations/${id}/members/`),
    enabled: Number.isFinite(id),
  })

const invalidateOrgs = (queryClient: ReturnType<typeof useQueryClient>) => {
  queryClient.invalidateQueries({ queryKey: ['organizations'] })
  queryClient.invalidateQueries({ queryKey: ['organization'] })
  queryClient.invalidateQueries({ queryKey: ['orgMembers'] })
  // Project visibility hangs off org membership, so lists can change too.
  queryClient.invalidateQueries({ queryKey: ['projects'] })
}

export const useCreateOrganization = () =>
  useInvalidatingMutation(
    (body: Record<string, unknown>) =>
      api.post<Organization>('/api/organizations/', body),
    invalidateOrgs,
  )

export const useUpdateOrganization = (id: number) =>
  useInvalidatingMutation(
    (body: Record<string, unknown>) =>
      api.patch<Organization>(`/api/organizations/${id}/`, body),
    invalidateOrgs,
  )

export const useDeleteOrganization = () =>
  useInvalidatingMutation((id: number) => api.delete(`/api/organizations/${id}/`), invalidateOrgs)

export const useAddOrgMember = (orgId: number) =>
  useInvalidatingMutation(
    (body: { user: number; role: string }) =>
      api.post<OrgMember>(`/api/organizations/${orgId}/members/`, body),
    invalidateOrgs,
  )

export const useUpdateOrgMemberRole = (orgId: number) =>
  useInvalidatingMutation(
    ({ memberId, role }: { memberId: number; role: string }) =>
      api.patch<OrgMember>(`/api/organizations/${orgId}/members/${memberId}/`, { role }),
    invalidateOrgs,
  )

export const useRemoveOrgMember = (orgId: number) =>
  useInvalidatingMutation(
    (memberId: number) => api.delete(`/api/organizations/${orgId}/members/${memberId}/`),
    invalidateOrgs,
  )
