import type { EvidenceSource, RetrievalHit, RetrievalResponse } from "./retrieval";

export interface CurrentEvidence {
  fact_id: string;
  source: string;
  text: string;
}

export interface FieldSuggestion {
  field: "summary" | "work_type" | "affected_business_or_it_services";
  current: string | string[] | null;
  suggested: string | string[] | null;
  state: "keep" | "propose_correction" | "propose_completion" | "needs_clarification" | "needs_review";
  evidence: CurrentEvidence[];
}

export interface FilteredCandidate extends RetrievalHit {
  description: string;
  services: string[];
  original_rank: number;
  filter_rank: number | null;
  role: "primary" | "reserve" | "not_selected";
}

export interface FilteredComment {
  id: string;
  text: string;
  services: string[];
  status: "reference" | "conditional" | "uncertain" | "not_selected";
  condition: string;
  reason: string;
  evidence: CurrentEvidence[];
  requires_current_verification: boolean;
  execution_authorized: false;
  sources: Array<{ document_id: string; original_rank: number; occurrences: number; examples: EvidenceSource[] }>;
}

export interface FilterResult {
  status: "ready" | "unfiltered_fallback" | "needs_review";
  candidates: FilteredCandidate[];
  comments: FilteredComment[];
  primary_document_ids: string[];
  active_comment_ids: string[];
  questions: string[];
  reason: string;
  service: string | null;
}

export interface TicketAnalysisResponse {
  status: "ready" | "needs_review" | "partial";
  clean: { status: "ready" | "unavailable"; fields: FieldSuggestion[]; questions: string[]; reason: string };
  filter: FilterResult | null;
  retrieval: RetrievalResponse | null;
  conflicts: Array<{ field: string; clean: string | null; filter: string | null; action: string }>;
  model: string;
  reasoning_effort: string;
  cache_hit: boolean;
  elapsed_ms: number;
  compute_ms: number;
  timings: { clean_ms: number; retrieval_ms: number; filter_ms: number };
}
