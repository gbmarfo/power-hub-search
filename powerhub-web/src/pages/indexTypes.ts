export type FolderOption = {
  id: string;
  name: string;
  path: string;
  file_count: number;
};

export type IndexIntegration = {
  search_index_id: string;
  source: string;
  registered: boolean;
  text_index_ready: boolean;
  vector_index: { exists?: boolean; num_entities?: number };
  embedding_model?: string;
  chunk_size?: number;
  chunk_overlap?: number;
  admin_search_url: string;
  admin_index_url: string;
  api_search_url: string;
};

export type IndexLink = {
  id: string;
  title: string;
  description?: string;
  folder_id?: string | null;
  folder_path?: string;
  folder_name?: string;
  search_index_id: string;
  document_count: number;
  updated_at?: string;
  integration?: IndexIntegration;
};

export type IndexSearchResult = {
  id: string;
  name?: string;
  path?: string;
  score?: number;
  text?: string;
  download_url?: string;
  extension?: string;
};

export const INDEX_SEARCH_MODES = [
  { value: "similarity", label: "Similarity (vector)" },
  { value: "full_text", label: "Full text (BM25)" },
  { value: "hybrid", label: "Hybrid" },
  { value: "ranked_naive", label: "Ranked naive" },
  { value: "boolean_ranked", label: "Boolean ranked" },
  { value: "exact", label: "Exact" },
  { value: "fuzzy", label: "Fuzzy" },
] as const;
