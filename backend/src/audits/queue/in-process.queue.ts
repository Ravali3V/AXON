import { Injectable, Logger } from "@nestjs/common";
import {
  AuditQueue,
  EnqueueAuditPayload,
  EnqueueRescorePayload,
} from "./audit-queue.interface";

/**
 * Local-dev queue: fire-and-forget HTTP POST to the worker. Not safe for production
 * (no retry, no durability) — the Cloud Tasks implementation takes over in prod.
 */
@Injectable()
export class InProcessQueue implements AuditQueue {
  private readonly logger = new Logger(InProcessQueue.name);
  private readonly workerUrl: string;

  constructor() {
    this.workerUrl = process.env.WORKER_URL ?? "http://localhost:9090";
  }

  async enqueueAudit(payload: EnqueueAuditPayload): Promise<void> {
    const url = `${this.workerUrl}/v1/audits/run`;
    this.logger.log(`[in-process] POST ${url} auditId=${payload.auditId}`);
    // Fire and forget — we don't await the scrape (could be 30 min). The worker
    // responds immediately with 202 Accepted and runs the pipeline in the background.
    void fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch((err) =>
      this.logger.error(`[in-process] enqueueAudit failed auditId=${payload.auditId}`, err),
    );
  }

  async enqueueRescore(payload: EnqueueRescorePayload): Promise<void> {
    const url = `${this.workerUrl}/v1/audits/rescore`;
    this.logger.log(`[in-process] POST ${url} auditId=${payload.auditId}`);
    void fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).catch((err) =>
      this.logger.error(`[in-process] enqueueRescore failed auditId=${payload.auditId}`, err),
    );
  }
}
