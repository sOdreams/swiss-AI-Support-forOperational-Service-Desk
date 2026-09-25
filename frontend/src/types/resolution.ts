import type { EvidenceSupport, TicketAnalysisResponse, TicketSignals } from "./analysis";
import type { EvidenceSource } from "./retrieval";

export interface ResolutionSource {
  id: string;
  kind: "current_fact" | "historical_case" | "historical_comment";
  text: string;
  source?: string;
  document_id?: string;
  original_rank?: number;
  condition?: string;
  verification_excerpt?: string | null;
  sources?: Array<{ document_id: string; original_rank: number; occurrences: number; examples: EvidenceSource[] }>;
}

export interface ResolutionAction {
  id: string;
  kind: "diagnostic" | "procedure";
  next_step: string;
  reason: string;
  check_first: string | null;
  expected_outcome: string | null;
  fact_ids: string[];
  source_ids: string[];
  sources: ResolutionSource[];
  required_checks: string[];
  execution_authorized: false;
}

export interface ResolutionProposal {
  status: "ready";
  proposal_id: string;
  mode: "action_plan" | "needs_information";
  actions: ResolutionAction[];
  critical_question: string | null;
  reply_draft: string;
  model: string;
  index_version: string | null;
  ticket_fingerprint: string;
  requires_review: true;
  context_signals?: TicketSignals;
  evidence_support?: EvidenceSupport;
  execution_authorized: false;
}

export interface ResolutionResponse extends TicketAnalysisResponse {
  analysis_cache_hit: boolean;
  resolution: ResolutionProposal | {
    status: "unavailable"; actions: []; critical_question: null; reply_draft: string; reason: string;
  };
}

export interface ActionReview {
  action_id: string;
  decision: "unreviewed" | "use" | "edit" | "not_applicable";
  edited_next_step: string | null;
}

export interface ResolutionEdits {
  proposal_id: string;
  actions: ActionReview[];
  reply_draft: string;
}

export interface ResolutionFeedback {
  proposal: ResolutionProposal;
  actions: ActionReview[];
  reply_draft: string;
  actual_outcome: string;
}
