/** Types mirroring the backend API contract v1 (`/api/v1`). */

export type ErrorDetails = Record<string, unknown> | null

export type ApiErrorCode =
  | 'validation_error'
  | 'case_not_found'
  | 'document_not_found'
  | 'unsupported_media_type'
  | 'payload_too_large'
  | 'empty_file'
  | 'no_documents'
  | 'case_not_ingested'
  | 'ingest_failed'
  | 'llm_unavailable'
  | 'internal_error'
  // Client-side codes, never sent by the backend.
  | 'network_error'
  | 'http_error'

export interface ErrorEnvelope {
  error: {
    code: string
    message: string
    details: ErrorDetails
  }
  request_id: string
}

// system

export type HealthStatus = 'ok' | 'degraded'

export interface OllamaHealth {
  reachable: boolean
  base_url: string
  model: string
  model_present: boolean | null
  models_installed: string[]
}

export interface EmbeddingsHealth {
  backend: string
  backend_configured: string
  model: string
  device: string
}

export interface HealthResponse {
  status: HealthStatus
  version: string
  ollama: OllamaHealth
  embeddings: EmbeddingsHealth
  vector_store: { path: string }
  chunking: { size: number; overlap: number }
}

export interface RoutingStatus {
  mode: string
  model_bg: string
  model_en: string
}

export interface ModelsResponse {
  active: string
  reachable: boolean
  installed: string[]
  routing: RoutingStatus
}

// cases

export type CaseStatus = 'empty' | 'uploaded' | 'ingested' | 'stale'

export interface CaseCreate {
  title: string
  description?: string
}

export interface CaseUpdate {
  title?: string
  description?: string
}

export interface CaseResponse {
  id: string
  title: string
  description: string | null
  created_at: string
  updated_at: string
  document_count: number
  status: CaseStatus
  chunk_count: number
  ingested_at: string | null
}

export interface Pagination {
  skip?: number
  limit?: number
}

// documents

export interface DocumentResponse {
  id: string
  case_id: string
  filename: string
  content_type: string
  size_bytes: number
  sha256: string
  uploaded_at: string
  language?: string
}

// rag

export interface IngestResponse {
  case_id: string
  documents_processed: number
  chunks_indexed: number
  embedding_backend: string
  embedding_model: string
  chunk_size: number
  chunk_overlap: number
  vector_store_path: string
  persisted: boolean
  duration_ms: number
}

export interface IndexStatsResponse {
  case_id: string
  collection: string
  chunk_count: number
  embedding_backend: string
  embedding_model: string
  ingested_at: string | null
}

export interface Citation {
  document_id: string
  document_filename: string
  chunk_id: string
  chunk_index: number
  quote: string
  relevance: number | null
  verbatim: boolean
}

export type AnswerLanguage = 'bg' | 'en' | 'auto'

export interface SummarizeRequest {
  top_k?: number
  answer_language?: AnswerLanguage
}

export interface SummarizeResponse {
  case_id: string
  summary: string
  citations: Citation[]
  model: string
  stubbed: boolean
  routed: boolean
  chunks_used: number
  duration_ms: number
  answer_language?: string
}

// search

export type SearchMode = 'semantic' | 'keyword' | 'hybrid'

export interface SearchHighlight {
  start: number
  end: number
}

export interface SearchResult {
  document_id: string
  document_filename: string
  chunk_id: string
  chunk_index: number | null
  text: string
  score: number
  highlights: SearchHighlight[]
  language: string
}

export interface SearchRequest {
  query: string
  top_k?: number
  mode?: SearchMode
}

export interface SearchResponse {
  query: string
  results: SearchResult[]
  duration_ms: number
  mode: string
}

// ask

export type AnswerStatus = 'answered' | 'not_found'

export interface AskRequest {
  question: string
  top_k?: number
  answer_language?: AnswerLanguage
}

export interface AskResponse {
  question: string
  answer: string
  answer_status: AnswerStatus
  citations: Citation[]
  retrieved_quotes: Citation[]
  model: string
  stubbed: boolean
  routed: boolean
  answer_language: string
  prompt_version: string
  language_warning: string | null
  retrieval_ms: number
  generation_ms: number
  duration_ms: number
}

// verify

export type Verdict = 'supported' | 'denied' | 'inconclusive'

export interface VerifyRequest {
  claim: string
  top_k?: number
  answer_language?: AnswerLanguage
}

export interface VerifyResponse {
  case_id: string
  claim: string
  verdict: Verdict
  rationale: string
  supporting_quotes: Citation[]
  denying_quotes: Citation[]
  retrieved_quotes: Citation[]
  model: string
  stubbed: boolean
  routed: boolean
  duration_ms: number
  answer_language?: string
}
