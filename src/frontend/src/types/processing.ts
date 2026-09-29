export type RelevanceRating = "highly_relevant" | "medium_relevant" | "poor_relevant";

export interface AiSolutionFeedback {
  solution_id: string;
  text: string;
  relevance: RelevanceRating;
  selected: boolean;
}

export interface RagFeedbackContext {
  work_type: string | null;
  request_type: string | null;
  priority: string | null;
  status: string;
  business_entity: string | null;
  service_teams: string[];
  affected_services: string[];
}

export interface ProcessedTicketRecord {
  issue_id: string;
  issue_key: string;
  summary: string;
  selected_solution: string | null;
  real_solution: string | null;
  affected_business_aspect: string;
  selected_affected_area_id?: string | null;
  original_ticket?: Record<string, unknown>;
  ai_analysis?: Record<string, unknown>;
  solution_feedback: AiSolutionFeedback[];
  knowledge_candidate: boolean;
  processed_at: string;
  sync_status: "api" | "local";
}

export interface ProcessTicketPayload {
  issue_id: string;
  issue_key: string;
  selected_solution_id: string | null;
  selected_solution: string | null;
  real_solution: string | null;
  affected_business_aspect: string;
  selected_affected_area_id?: string | null;
  original_ticket?: Record<string, unknown>;
  ai_analysis?: Record<string, unknown>;
  solution_feedback: AiSolutionFeedback[];
  rag_context: RagFeedbackContext;
  knowledge_candidate: boolean;
  processed_at: string;
  source: "human_in_the_loop_rag_feedback";
}
