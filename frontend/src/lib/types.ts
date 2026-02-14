/**
 * Shared TypeScript types matching backend Pydantic schemas.
 */

// ─── User ────────────────────────────────────────────────────────────────────

export type Tier = "FREE" | "PRO";

export interface User {
  id: string;
  email: string;
  tier: Tier;
  created_at: string;
}

// ─── Session ─────────────────────────────────────────────────────────────────

export interface GameSession {
  id: string;
  user_id: string;
  game_name: string;
  created_at: string;
  expires_at: string;
}

// ─── Ruleset ─────────────────────────────────────────────────────────────────

export type SourceType = "BASE" | "EXPANSION" | "ERRATA";
export type RulesetStatus = "PROCESSING" | "INDEXED" | "FAILED" | "EXPIRED";

export interface RulesetMetadata {
  id: string;
  filename: string;
  game_name: string;
  source_type: SourceType;
  status: RulesetStatus;
  chunk_count: number;
  error_message: string | null;
}

// ─── Judge ───────────────────────────────────────────────────────────────────

export interface Citation {
  source: string;
  page: number | null;
  section: string | null;
  snippet: string;
  is_official: boolean;
}

export interface Conflict {
  description: string;
  resolution: string;
}

export interface Verdict {
  verdict: string;
  reasoning_chain: string | null;
  confidence: number;
  confidence_reason: string | null;
  citations: Citation[];
  conflicts: Conflict[] | null;
  follow_up_hint: string | null;
  query_id: string;
}

// ─── Library ─────────────────────────────────────────────────────────────────

export interface LibraryGame {
  id: string;
  game_name: string;
  is_favorite: boolean;
  official_ruleset_ids: string[] | null;
  personal_ruleset_ids: string[] | null;
  last_queried: string | null;
}

// ─── Catalog ─────────────────────────────────────────────────────────────────

export interface CatalogGame {
  id: string;
  game_name: string;
  game_slug: string;
  publisher_name: string;
  source_type: SourceType;
  version: string;
}

// ─── Errors ──────────────────────────────────────────────────────────────────

export type ErrorCode =
  | "VALIDATION_ERROR"
  | "UNAUTHORIZED"
  | "RATE_LIMITED"
  | "SESSION_EXPIRED"
  | "PROCESSING_FAILED"
  | "NOT_A_RULEBOOK"
  | "BLOCKED_FILE"
  | "INTERNAL_ERROR";

export interface ApiErrorDetail {
  code: ErrorCode;
  message: string;
  retry_after_seconds?: number;
}

// ─── Confidence ──────────────────────────────────────────────────────────────

export type ConfidenceLevel = "high" | "medium" | "low" | "uncertain";

export function getConfidenceLevel(confidence: number): ConfidenceLevel {
  if (confidence >= 0.9) return "high";
  if (confidence >= 0.7) return "medium";
  if (confidence >= 0.5) return "low";
  return "uncertain";
}

export function getConfidenceColor(level: ConfidenceLevel): string {
  switch (level) {
    case "high":
      return "#22c55e"; // green
    case "medium":
      return "#eab308"; // yellow
    case "low":
      return "#f97316"; // orange
    case "uncertain":
      return "#ef4444"; // red
  }
}
