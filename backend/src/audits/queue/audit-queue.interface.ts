/**
 * AuditQueue abstraction — production uses Cloud Tasks, local dev uses in-process HTTP.
 * Swap at module-wire time via QUEUE_BACKEND env.
 */
export interface AuditQueue {
  enqueueAudit(payload: EnqueueAuditPayload): Promise<void>;
  enqueueRescore(payload: EnqueueRescorePayload): Promise<void>;
}

export interface EnqueueAuditPayload {
  auditId: string;
  orgId: string;
  brandName: string;
}

export interface EnqueueRescorePayload {
  auditId: string;
  orgId: string;
  version: number;
}

export const AUDIT_QUEUE = Symbol("AUDIT_QUEUE");
