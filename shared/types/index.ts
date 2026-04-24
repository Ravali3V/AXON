// Shared contracts between frontend and backend. Keep minimal and API-shape-only.

export type AuditStatus =
  | "queued"
  | "resolving"
  | "scraping"
  | "scoring"
  | "enriching"
  | "rendering"
  | "complete"
  | "failed";

export type AuditGrade = "A" | "B" | "C" | "D" | "F";

export type ScoreStatus = "scored" | "na" | "warning";

export type FindingType = "strength" | "weakness" | "recommendation" | "quick_win";

export interface AuditSummary {
  id: string;
  brandName: string;
  status: AuditStatus;
  scoreTotal: number | null;
  scorePossible: number | null;
  grade: AuditGrade | null;
  startedAt: string;
  finishedAt: string | null;
  version: number;
}

export interface AuditEvent {
  ts: string;
  stage: string;
  message: string;
  level: "info" | "warn" | "error";
}

export interface ScoreBreakdown {
  section: string;
  criterion: string;
  pointsEarned: number;
  pointsPossible: number;
  status: ScoreStatus;
  evidence?: Record<string, unknown>;
}

export interface Finding {
  type: FindingType;
  section: string;
  text: string;
  priority: number;
  source: "rule" | "llm";
}

export interface CreateAuditRequest {
  brandName: string;
}

export interface CreateAuditResponse {
  auditId: string;
  status: AuditStatus;
}

export interface AuditDetail extends AuditSummary {
  scores: ScoreBreakdown[];
  findings: Finding[];
  asinCount: number;
  reviewCount: number;
  reportPdfUrl: string | null;
}
