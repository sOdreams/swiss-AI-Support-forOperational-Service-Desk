export interface EvidenceSource {
  row_index: number;
  ticket_id: string;
  comment_index: number;
  author: string | null;
  services: string[];
  teams: string[];
}

export interface RetrievalHit {
  document_id: string;
  rank: number;
  score: number;
  summary: string;
  matched_text: string;
  historical_count: number;
  evidence: Array<{ body: string; occurrences: number; sources: EvidenceSource[] }>;
}

export interface RetrievalResponse {
  index_version: string;
  model: string;
  score_type: "cosine";
  hits: RetrievalHit[];
}

export interface RetrievalProvenance {
  index_version: string;
  model: string;
  shown_document_ids: string[];
  selected_document_ids: string[];
}
