import { Injectable, Logger } from "@nestjs/common";
import { CloudTasksClient } from "@google-cloud/tasks";
import {
  AuditQueue,
  EnqueueAuditPayload,
  EnqueueRescorePayload,
} from "./audit-queue.interface";

/**
 * Production queue: Google Cloud Tasks. Gives per-task retries, rate limiting, and
 * a native HTTP trigger to the worker's Cloud Run URL.
 */
@Injectable()
export class CloudTasksQueue implements AuditQueue {
  private readonly logger = new Logger(CloudTasksQueue.name);
  private readonly client: CloudTasksClient;
  private readonly projectId: string;
  private readonly location: string;
  private readonly queueName: string;
  private readonly workerUrl: string;
  private readonly invokerServiceAccount?: string;

  constructor() {
    this.client = new CloudTasksClient();
    this.projectId = mustHaveEnv("GCP_PROJECT_ID");
    this.location = process.env.GCP_REGION ?? "us-central1";
    this.queueName = process.env.CLOUD_TASKS_QUEUE ?? "axon-audit-queue";
    this.workerUrl = mustHaveEnv("WORKER_URL");
    this.invokerServiceAccount = process.env.CLOUD_TASKS_INVOKER_SA;
  }

  async enqueueAudit(payload: EnqueueAuditPayload): Promise<void> {
    await this.enqueue(`${this.workerUrl}/v1/audits/run`, payload, `audit-${payload.auditId}`);
  }

  async enqueueRescore(payload: EnqueueRescorePayload): Promise<void> {
    await this.enqueue(
      `${this.workerUrl}/v1/audits/rescore`,
      payload,
      `rescore-${payload.auditId}-${payload.version}`,
    );
  }

  private async enqueue(url: string, body: unknown, taskName: string): Promise<void> {
    const parent = this.client.queuePath(this.projectId, this.location, this.queueName);
    const task = {
      name: `${parent}/tasks/${taskName}`,
      httpRequest: {
        httpMethod: "POST" as const,
        url,
        headers: { "Content-Type": "application/json" },
        body: Buffer.from(JSON.stringify(body)).toString("base64"),
        ...(this.invokerServiceAccount
          ? { oidcToken: { serviceAccountEmail: this.invokerServiceAccount } }
          : {}),
      },
    };
    try {
      await this.client.createTask({ parent, task });
      this.logger.log(`[cloud-tasks] enqueued ${taskName}`);
    } catch (err) {
      this.logger.error(`[cloud-tasks] enqueue failed ${taskName}`, err as Error);
      throw err;
    }
  }
}

function mustHaveEnv(key: string): string {
  const v = process.env[key];
  if (!v) throw new Error(`Missing required env var: ${key}`);
  return v;
}
