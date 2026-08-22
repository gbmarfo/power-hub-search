export type SearchMode =
  | "ranked_naive"
  | "full_text"
  | "boolean_ranked"
  | "exact"
  | "fuzzy"
  | "similarity"
  | "exact_similarity"
  | "hybrid";

export interface HealthResponse {
  status: string;
  version: string;
  milvus: {
    status: string;
    version?: string;
    detail?: string;
  };
}

export interface SearchIndex {
  id: number;
  global_id: string;
  title: string | null;
  description: string | null;
  table_name: string | null;
  text_columns: string | null;
  id_col: string | null;
  org_id: string | null;
  source: string | null;
  schema_name: string | null;
  created_by: string | null;
}

export interface IndexDetailResponse {
  index: SearchIndex;
  vector_stats: {
    exists: boolean;
    collection?: string;
    num_entities?: number;
  };
}

export interface SearchResult {
  id: string | number;
  text: string;
  score?: number;
}

export interface UserRecord {
  id: number;
  user_id: string;
  username: string;
  full_name: string | null;
  email: string | null;
  organization_id: string | null;
  role: string | null;
  is_active: number | null;
}

export interface OrganizationRecord {
  id: number;
  organization_id: string;
  name: string | null;
  description: string | null;
  contact_email: string | null;
  organization_type: string | null;
}

export interface MultimodalStatus {
  enabled: boolean;
  encoder: {
    available?: boolean;
    backend?: string;
    dimension?: number;
    visual_bge_weights?: boolean;
  };
  reranker_configured: boolean;
  metric_type: string;
  default_top_k: number;
}

export interface MultimodalRerankResponse {
  results: Record<string, unknown>[];
  reranked_results: Record<string, unknown>[];
  ranked_indices: number[];
  best_result: Record<string, unknown> | null;
  explanation: string;
  panoramic_url: string | null;
}
