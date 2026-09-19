import type { AiProposal } from "../types/ai";
import type { ProcessTicketPayload } from "../types/processing";
import type { HumanReview } from "../types/review";
import type { Ticket } from "../types/ticket";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) throw new Error(`API request failed: ${response.status} ${response.statusText}`);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export interface LearningFeedbackPayload {
  message: string;
  visible_ticket_count: number;
  total_ticket_count: number;
  created_at: string;
  source: "queue_assistant";
}

export const getTickets = () => request<Ticket[]>("/tickets");
export const getTicket = (issueId: string) => request<Ticket>(`/tickets/${encodeURIComponent(issueId)}`);
export const analyzeTicket = (issueId: string) => request<AiProposal>(`/tickets/${encodeURIComponent(issueId)}/assist`, { method: "POST" });
export const saveHumanReview = (review: HumanReview) => request<void>("/feedback", { method: "POST", body: JSON.stringify(review) });
export const submitLearningFeedback = (payload: LearningFeedbackPayload) => request<void>("/feedback/learning", { method: "POST", body: JSON.stringify(payload) });
export const submitProcessedTicket = (payload: ProcessTicketPayload) => request<void>("/tickets/process", { method: "POST", body: JSON.stringify(payload) });
