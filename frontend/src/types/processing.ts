import type { RetrievalProvenance } from "./retrieval";

export interface ProcessedTicketRecord {
  issue_id: string;
  issue_key: string;
  summary: string;
  recommended_solution: string | null;
  real_solution: string | null;
  affected_business_aspect: string;
  processed_at: string;
  sync_status: "api" | "local";
}

export interface ProcessTicketPayload {
  issue_id: string;
  issue_key: string;
  recommended_solution: string | null;
  real_solution: string | null;
  affected_business_aspect: string;
  processed_at: string;
  source: "human_resolution_workflow";
  retrieval?: RetrievalProvenance;
}
