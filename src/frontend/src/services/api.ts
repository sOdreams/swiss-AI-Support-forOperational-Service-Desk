import type { AiProposal } from "../types/ai";
import type { ProcessTicketPayload } from "../types/processing";
import type { HumanReview } from "../types/review";
import type { Ticket } from "../types/ticket";
import type {
  AffectedArea,
  EvidenceTicket,
  Prediction,
  RecommendedSolution,
  TriageAnalysis,
  TriageResult,
} from "../types/triage";

const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function asString(value: unknown): string | null {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
}

function prediction(value: unknown): Prediction {
  if (isRecord(value)) {
    const confidence = typeof value.confidence === "number" ? value.confidence : null;
    return {
      value: asString(value.value),
      confidence,
      method: asString(value.method),
      reason: asString(value.reason),
    };
  }
  return { value: asString(value), confidence: null, method: null, reason: null };
}

function normalizeSolutions(value: unknown, fallbackResolutionText?: unknown): RecommendedSolution[] {
  const output: RecommendedSolution[] = [];
  if (Array.isArray(value)) {
    value.forEach((item, index) => {
      if (typeof item === "string") {
        output.push({ id: `solution_${index + 1}`, description: item, confidence: null });
        return;
      }
      if (!isRecord(item)) return;
      const description = asString(item.description ?? item.text ?? item.solution);
      if (!description) return;
      output.push({
        id: asString(item.id) ?? `solution_${index + 1}`,
        title: asString(item.title),
        description,
        confidence: typeof item.confidence === "number" ? item.confidence : null,
      });
    });
    return output;
  }

  const resolutionText = asString(fallbackResolutionText);
  if (resolutionText) output.push({ id: "solution_1", title: "AI suggested resolution", description: resolutionText, confidence: null });
  return output;
}

function normalizeAreas(value: unknown): AffectedArea[] {
  const output: AffectedArea[] = [];
  if (!Array.isArray(value)) return output;
  value.forEach((item, index) => {
    if (typeof item === "string") {
      output.push({ id: `area_${index + 1}`, label: item, confidence: null });
      return;
    }
    if (!isRecord(item)) return;
    const label = asString(item.label ?? item.name ?? item.area);
    if (!label) return;
    output.push({
      id: asString(item.id) ?? `area_${index + 1}`,
      label,
      confidence: typeof item.confidence === "number" ? item.confidence : null,
      reason: asString(item.reason),
    });
  });
  return output;
}

function normalizeEvidence(value: unknown): EvidenceTicket[] {
  const output: EvidenceTicket[] = [];
  if (!Array.isArray(value)) return output;
  value.forEach((item, index) => {
    if (!isRecord(item)) return;
    output.push({
      ticket_id: asString(item.ticket_id ?? item.id ?? item.issue_key) ?? `evidence_${index + 1}`,
      similarity: typeof item.similarity === "number" ? item.similarity : null,
      summary: asString(item.summary ?? item.title),
      resolution_excerpt: asString(item.resolution_excerpt ?? item.resolution ?? item.excerpt),
    });
  });
  return output;
}

/**
 * Normalizes both the recommended nested /triage response and the simpler flat
 * JSON shape produced by the L2 prompt. This keeps Gemini/backend integration
 * flexible without leaking backend-specific shapes into React components.
 */
export function normalizeTriageResult(payload: unknown, fallbackTicketId: string): TriageResult {
  const root = isRecord(payload) ? payload : {};
  const rawAnalysis = isRecord(root.analysis) ? root.analysis : root;

  const analysis: TriageAnalysis = {
    work_type: prediction(rawAnalysis.work_type),
    affected_service: prediction(rawAnalysis.affected_service ?? rawAnalysis.service),
    service_team: prediction(rawAnalysis.service_team ?? rawAnalysis.team),
    assignee: prediction(rawAnalysis.assignee),
    urgency: prediction(rawAnalysis.urgency),
    impact: prediction(rawAnalysis.impact),
    priority: prediction(rawAnalysis.priority),
    resolution_status: prediction(rawAnalysis.resolution_status ?? rawAnalysis.resolution),
  };

  const status = root.status === "error" ? "error" : "success";
  const errorRecord = isRecord(root.error) ? root.error : null;

  return {
    ticket_id: asString(root.ticket_id) ?? fallbackTicketId,
    status,
    analysis,
    recommended_solutions: normalizeSolutions(root.recommended_solutions ?? root.solutions, root.resolution_text),
    affected_areas: normalizeAreas(root.affected_areas ?? root.affected_business_areas ?? root.business_areas),
    evidence: normalizeEvidence(root.evidence ?? root.sources ?? root.historical_context),
    error: errorRecord
      ? { code: asString(errorRecord.code) ?? undefined, message: asString(errorRecord.message) ?? "Ticket analysis failed." }
      : null,
  };
}

export interface TriageRequest {
  ticket_id: string;
  ticket: Record<string, unknown>;
}

export async function triageTicket(ticket: Ticket): Promise<TriageResult> {
  const payload: TriageRequest = {
    ticket_id: ticket.issue_id,
    ticket: ticket.raw ?? {},
  };
  const response = await request<unknown>("/triage", { method: "POST", body: JSON.stringify(payload) });
  return normalizeTriageResult(response, ticket.issue_id);
}

export async function triageTicketsBatch(tickets: Ticket[]): Promise<TriageResult[]> {
  const body = {
    tickets: tickets.map((ticket) => ({ ticket_id: ticket.issue_id, ticket: ticket.raw ?? {} })),
  };

  try {
    const response = await request<unknown>("/triage/batch", { method: "POST", body: JSON.stringify(body) });
    const root = isRecord(response) ? response : {};
    const results = Array.isArray(root.results) ? root.results : Array.isArray(response) ? response : [];
    if (!results.length) throw new Error("Batch endpoint returned no results.");
    return results.map((item, index) => normalizeTriageResult(item, tickets[index]?.issue_id ?? `ticket-${index + 1}`));
  } catch {
    const settled = await Promise.allSettled(tickets.map((ticket) => triageTicket(ticket)));
    return settled.map((result, index) => {
      if (result.status === "fulfilled") return result.value;
      return {
        ticket_id: tickets[index]!.issue_id,
        status: "error" as const,
        analysis: {
          work_type: { value: null },
          affected_service: { value: null },
          service_team: { value: null },
          assignee: { value: null },
          urgency: { value: null },
          impact: { value: null },
          priority: { value: null },
          resolution_status: { value: null },
        },
        recommended_solutions: [],
        affected_areas: [],
        evidence: [],
        error: { message: result.reason instanceof Error ? result.reason.message : "Ticket analysis failed." },
      };
    });
  }
}

export interface LearningFeedbackPayload {
  message: string;
  visible_ticket_count: number;
  total_ticket_count: number;
  created_at: string;
  source: "queue_assistant";
}

// Legacy endpoints kept for backward compatibility with earlier backend builds.
export const getTickets = () => request<Ticket[]>("/tickets");
export const getTicket = (issueId: string) => request<Ticket>(`/tickets/${encodeURIComponent(issueId)}`);
export const analyzeTicket = (issueId: string) => request<AiProposal>(`/tickets/${encodeURIComponent(issueId)}/assist`, { method: "POST" });
export const saveHumanReview = (review: HumanReview) => request<void>("/feedback", { method: "POST", body: JSON.stringify(review) });
export const submitLearningFeedback = (payload: LearningFeedbackPayload) => request<void>("/feedback/learning", { method: "POST", body: JSON.stringify(payload) });

export const submitRagFeedback = (payload: ProcessTicketPayload) =>
  request<void>("/feedback/rag", { method: "POST", body: JSON.stringify(payload) });

export const submitProcessedTicket = submitRagFeedback;
