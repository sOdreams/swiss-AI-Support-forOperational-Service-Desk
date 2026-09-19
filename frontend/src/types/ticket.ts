export type Priority = "Highest" | "High" | "Medium" | "Low" | "Lowest" | string;

export interface JiraUser {
  id: string;
  display_name: string;
}

export interface LinkedIssue {
  relation: string;
  issue_key: string;
  summary: string;
  status?: string | null;
}

export interface JiraComment {
  id: string;
  author: JiraUser;
  body: string;
  created_at: string;
  visibility?: "public" | "internal" | null;
  semantic_role?: "comment" | "action" | "result" | null;
}

/**
 * Shared ticket contract for Frontend, AI and API integration.
 * These are the 22 original Jira fields agreed by the team.
 * Null means "not recorded", never an inferred low/false value.
 */
export interface Ticket {
  issue_id: string;
  issue_key: string;
  work_type: string | null;
  request_type: string | null;
  summary: string;
  description: string | null;
  affected_business_or_it_services: string[];
  business_entity: string | null;
  business_critical_for_entity: boolean | null;
  service_teams: string[];
  reporter: JiraUser | null;
  assignee: JiraUser | null;
  priority: Priority | null;
  urgency: string | null;
  impact: string | null;
  severity: string | null;
  created_date: string;
  status: string;
  linked_issues: LinkedIssue[];
  resolution: string | null;
  due_date: string | null;
  all_comments: JiraComment[];
}
