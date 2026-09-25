import type { CurrentEvidence } from "./analysis";

export interface TriageResult {
  priority: {
    status: "suggested" | "needs_information" | "needs_review" | "unavailable";
    urgency: { value: string | null; evidence: CurrentEvidence[] };
    impact: { value: string | null; evidence: CurrentEvidence[] };
    value: string | null;
    proposed_value: string | null;
    rule_version: string;
    rule_source: string;
    reason: string;
    requires_review: true;
  };
  routing: {
    status: "suggested" | "needs_information" | "needs_review" | "unavailable";
    service: string | null;
    team: string | null;
    reason: string;
    service_evidence: CurrentEvidence[];
    catalogue_evidence: Array<{ team: string; historical_rows: number; example_row_indices: number[] }>;
    historical_contributors: Array<{ author: string; evidence: Array<{
      comment_id: string; text: string; condition: string; document_id: string; original_rank: number; row_index: number;
    }> }>;
    index_version: string | null;
    assignee: null;
    assignment_authorized: false;
    requires_review: true;
  };
}
