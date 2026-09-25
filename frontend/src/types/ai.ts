import type { KnowledgeSource } from "./knowledge";
import type { Priority } from "./ticket";

export type ResolutionOptionKind = "recommended" | "clarification" | "escalation";

export interface ResolutionOption {
  id: string;
  title: string;
  description: string;
  kind: ResolutionOptionKind;
  prerequisites: string[];
  expected_outcome: string | null;
  source_ids: string[];
}

export interface AiProposal {
  ticket_id: string;
  issue_key: string;
  case_summary: string;

  proposed_work_type: string | null;
  proposed_request_type: string | null;

  proposed_priority: Priority | null;
  priority_reason: string | null;

  proposed_service_team: string | null;
  service_team_reason: string | null;
  proposed_assignee: string | null;
  assignee_reason: string | null;

  proposed_urgency: string | null;
  urgency_reason: string | null;

  proposed_impact: string | null;
  impact_reason: string | null;

  proposed_severity: string | null;
  severity_reason: string | null;
  proposed_resolution: string | null;
  resolution_reason: string | null;

  affected_services_suggestion: string[];
  pending_questions: string[];
  resolution_options: ResolutionOption[];
  sources: KnowledgeSource[];
  draft_response: string;
  confidence: number;
  analyzed_at: string;
}
