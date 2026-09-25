export interface KnowledgeSource {
  id: string;
  title: string;
  document_type: "knowledge_article" | "historical_ticket" | "procedure" | string;
  section?: string | null;
  relevance_score?: number | null;
  excerpt?: string | null;
}
