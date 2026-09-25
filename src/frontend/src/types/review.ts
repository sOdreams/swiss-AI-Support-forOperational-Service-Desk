import type { Priority } from "./ticket";

export type ReviewDecision = "pending" | "approved" | "edited" | "rejected";

export interface HumanCorrections {
  work_type?: string | null;
  request_type?: string | null;
  priority?: Priority | null;
  service_team?: string | null;
  urgency?: string | null;
  impact?: string | null;
  severity?: string | null;
  draft_response?: string;
}

export interface HumanReview {
  ticket_id: string;
  decision: ReviewDecision;
  corrections: HumanCorrections;
  reviewer?: string | null;
  reviewed_at?: string | null;
  comment?: string | null;
}
