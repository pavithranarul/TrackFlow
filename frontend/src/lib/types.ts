export type Role = 'OWNER' | 'MANAGER' | 'DEVELOPER' | 'VIEWER'
export type IssueStatus = 'TODO' | 'IN_PROGRESS' | 'TESTING' | 'DONE'
export type Priority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT' | 'CRITICAL'
export type IssueType = 'TASK' | 'BUG' | 'FEATURE' | 'CHORE'
export type Visibility = 'PRIVATE' | 'PUBLIC'
export type ProjectStatus = 'ACTIVE' | 'ARCHIVED'

export interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  /** Platform admin. A rendering hint only — the API re-checks it. */
  is_superuser?: boolean
}

export type OrgRole = 'ADMIN' | 'MEMBER'

export interface Organization {
  id: number
  name: string
  slug: string
  is_active: boolean
  member_count: number
  project_count: number
  my_role: OrgRole | null
  created_at: string
  description?: string
  updated_at?: string
  members?: OrgMember[]
}

export interface OrgMember {
  id: number
  user: number
  username: string | null
  email: string | null
  role: OrgRole
  joined_at: string
}

export interface Project {
  id: number
  name: string
  key: string
  owner: string
  organization: number
  organization_name: string | null
  organization_slug: string | null
  status: ProjectStatus
  visibility: Visibility
  created_at: string
  updated_at: string
  description?: string
  members?: Member[]
}

export interface Member {
  id: number
  user: number
  username: string
  role: Role
  joined_at: string
}

/** The lightweight shape returned by list endpoints. */
export interface IssueSummary {
  id: number
  key: string
  project: number
  project_key: string
  title: string
  type: IssueType
  status: IssueStatus
  priority: Priority
  reporter: string | null
  assignee: string | null
  created_at: string
  updated_at: string
}

export interface Comment {
  id: number
  issue: number
  author: User | null
  body: string
  created_at: string
  updated_at: string
}

export interface Activity {
  id: number
  actor: string | null
  action:
    | 'CREATED'
    | 'STATUS_CHANGED'
    | 'ASSIGNED'
    | 'UNASSIGNED'
    | 'PRIORITY_CHANGED'
    | 'UPDATED'
    | 'COMMENTED'
  field: string
  old_value: string
  new_value: string
  created_at: string
}

export interface Issue extends Omit<IssueSummary, 'reporter' | 'assignee'> {
  description: string
  reporter: User | null
  assignee: User | null
  comments: Comment[]
  activities: Activity[]
  /** Which statuses this issue may move to right now, per the backend graph. */
  allowed_transitions: IssueStatus[]
  closed_at: string | null
}

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export const STATUSES: IssueStatus[] = ['TODO', 'IN_PROGRESS', 'TESTING', 'DONE']

export const STATUS_LABEL: Record<IssueStatus, string> = {
  TODO: 'To Do',
  IN_PROGRESS: 'In Progress',
  TESTING: 'Testing',
  DONE: 'Done',
}

export const PRIORITIES: Priority[] = ['LOW', 'MEDIUM', 'HIGH', 'URGENT', 'CRITICAL']
export const TYPES: IssueType[] = ['TASK', 'BUG', 'FEATURE', 'CHORE']
export const ROLES: Role[] = ['OWNER', 'MANAGER', 'DEVELOPER', 'VIEWER']

export const ORG_ROLES: OrgRole[] = ['ADMIN', 'MEMBER']
