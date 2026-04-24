import type {
  AuditDetail,
  AuditSummary,
  CreateAuditRequest,
  CreateAuditResponse,
  Finding,
  ScoreBreakdown,
} from "@axon/shared";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const API = `${BASE}/api`;

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return (await res.json()) as T;
}

export function createAudit(req: CreateAuditRequest): Promise<CreateAuditResponse> {
  return request("/audits", { method: "POST", body: JSON.stringify(req) });
}

export function listAudits(): Promise<AuditSummary[]> {
  return request("/audits");
}

export interface BrandStoreJson {
  store_url: string | null;
  exists: boolean;
  page_count: number;
  has_hero: boolean;
  video_count: number;
  nav_depth: number;
  product_tile_count: number;
  about_us_text: string | null;
  brand_story_present: boolean;
  pages_visited: string[];
}

export interface AsinDetail {
  asin: string;
  title: string | null;
  rating: string | null;
  review_count: number | null;
  bsr: number | null;
  bsr_category: string | null;
  buybox_seller: string | null;
  image_count: number;
  bullet_count: number;
  has_aplus: boolean;
  has_brand_story: boolean;
  has_video: boolean;
  main_image_url: string | null;
}

export interface AuditDetailResponse {
  audit: {
    id: string;
    orgId: string;
    brandName: string;
    status: string;
    scoreTotal: number | null;
    scorePossible: number | null;
    grade: string | null;
    startedAt: string;
    finishedAt: string | null;
    reportPdfGcsPath: string | null;
    version: number;
    errorMessage: string | null;
  };
  scores: Array<{
    section: string;
    criterion: string;
    pointsEarned: string | number;
    pointsPossible: string | number;
    status: "scored" | "na" | "warning";
    evidence: Record<string, unknown> | null;
  }>;
  findings: Array<{
    type: "strength" | "weakness" | "recommendation" | "quick_win";
    section: string;
    text: string;
    priority: number;
    source: "rule" | "llm";
  }>;
  asinCount: number;
  reviewCount: number;
  brandData: {
    brandStoreUrl: string | null;
    brandStoreJson: BrandStoreJson | null;
    brandStoryDetected: boolean;
    videoCount: number;
    asinCount: number;
    scrapedAt: string;
  } | null;
  asins: AsinDetail[];
}

export function getAudit(id: string): Promise<AuditDetailResponse> {
  return request(`/audits/${id}`);
}

/**
 * Fetches the audit PDF as a Blob and triggers a browser download.
 * Works in both dev (file:// backed) and prod (GCS backed).
 */
export async function downloadAuditPdf(id: string, brandName: string): Promise<void> {
  const res = await fetch(`${API}/audits/${id}/pdf`);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${brandName.replace(/[^a-z0-9]/gi, "-").toLowerCase()}-brand-audit.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function submitOverrides(
  id: string,
  overrides: Array<{ fieldPath: string; originalValue: unknown; overrideValue: unknown }>,
): Promise<{ auditId: string; version: number }> {
  return request(`/audits/${id}/overrides`, {
    method: "POST",
    body: JSON.stringify({ overrides }),
  });
}

export interface ProgressEvent {
  ts: string;
  stage: string;
  message: string;
  level: "info" | "warn" | "error";
  status: string;
}

export function openEventStream(
  id: string,
  onEvent: (ev: ProgressEvent) => void,
  onError?: (err: Event) => void,
): () => void {
  const src = new EventSource(`${API}/audits/${id}/events`);
  src.addEventListener("progress", (e) => {
    try {
      onEvent(JSON.parse((e as MessageEvent).data));
    } catch {
      // ignore malformed frames
    }
  });
  src.onerror = (err) => onError?.(err);
  return () => src.close();
}

// Re-export for convenience
export type { AuditDetail, AuditSummary, Finding, ScoreBreakdown };
