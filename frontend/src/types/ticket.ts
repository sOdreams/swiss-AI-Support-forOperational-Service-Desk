export interface Ticket {
  id: string;
  title: string;
  description: string;
  created_at?: string;
  requester_id?: string;
  department?: string;
  service?: string;
  status?: "new" | "in_progress" | "resolved" | "closed" | string;
  metadata?: Record<string, unknown>;
}
