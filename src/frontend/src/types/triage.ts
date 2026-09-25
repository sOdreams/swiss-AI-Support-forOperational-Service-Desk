import type { Priority } from "./ticket";

export interface Prediction<T = string> {
  value: T | null;
  confidence?: number | null;
  method?: string | null;
  reason?: string | null;
}

export interface RecommendedSolution {
  id: string;
  title?: string | null;
  description: string;
  confidence?: number | null;
}

export interface AffectedArea {
  id: string;
  label: string;
  confidence?: number | null;
  reason?: string | null;
}

export interface EvidenceTicket {
  ticket_id: string;
  similarity?: number | null;
  summary?: string | null;
  resolution_excerpt?: string | null;
}

export interface TriageAnalysis {
  work_type: Prediction;
  affected_service: Prediction;
  service_team: Prediction;
  assignee: Prediction;
  urgency: Prediction;
  impact: Prediction;
  priority: Prediction<Priority>;
  resolution_status?: Prediction;
}

export interface TriageResult {
  ticket_id: string;
  status: "success" | "error";
  analysis: TriageAnalysis;
  recommended_solutions: RecommendedSolution[];
  affected_areas: AffectedArea[];
  evidence: EvidenceTicket[];
  error?: {
    code?: string;
    message: string;
  } | null;
}

export type TicketAnalysisStatus = "idle" | "queued" | "analyzing" | "success" | "error";
