import type { KnowledgeSource } from "./knowledge";
import type { Priority } from "./ticket";

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

  proposed_urgency: string | null;
  urgency_reason: string | null;

  proposed_impact: string | null;
  impact_reason: string | null;

  proposed_severity: string | null;
  severity_reason: string | null;

  affected_services_suggestion: string[];
  pending_questions: string[];
  sources: KnowledgeSource[];
  draft_response: string;
  confidence: number;
  analyzed_at: string;
}
