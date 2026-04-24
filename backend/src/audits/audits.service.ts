import { Inject, Injectable, Logger, NotFoundException } from "@nestjs/common";
import { DataSource } from "typeorm";
import { InjectDataSource } from "@nestjs/typeorm";
import { Observable, interval } from "rxjs";
import { Audit } from "../database/entities/audit.entity";
import { AuditBrandData } from "../database/entities/audit-brand-data.entity";
import { AuditEvent } from "../database/entities/audit-event.entity";
import { AuditFinding } from "../database/entities/audit-finding.entity";
import { AuditScore } from "../database/entities/audit-score.entity";
import { AuditAsin } from "../database/entities/audit-asin.entity";
import { AuditReview } from "../database/entities/audit-review.entity";
import { AuditManualOverride } from "../database/entities/audit-manual-override.entity";
import { withTenant } from "../database/tenant-context";
import { CreateAuditDto } from "./dto/create-audit.dto";
import { AUDIT_QUEUE, AuditQueue } from "./queue/audit-queue.interface";

export interface ProgressEvent {
  ts: string;
  stage: string;
  message: string;
  level: "info" | "warn" | "error";
  status: string;
}

@Injectable()
export class AuditsService {
  private readonly logger = new Logger(AuditsService.name);

  constructor(
    @InjectDataSource() private readonly ds: DataSource,
    @Inject(AUDIT_QUEUE) private readonly queue: AuditQueue,
  ) {}

  async create(orgId: string, dto: CreateAuditDto) {
    // Write the audit + queued event INSIDE a transaction, then commit.
    const created = await withTenant(this.ds, orgId, async (em) => {
      const audit = em.create(Audit, {
        orgId,
        brandName: dto.brandName.trim(),
        status: "queued",
      });
      const saved = await em.save(audit);

      await em.insert(AuditEvent, {
        auditId: saved.id,
        orgId,
        stage: "queued",
        message: `Audit queued for brand: ${saved.brandName}`,
        level: "info",
      });

      return {
        auditId: saved.id,
        status: saved.status,
        brandName: saved.brandName,
      };
    });

    // Enqueue AFTER the transaction commits — otherwise the worker can read
    // audit_id that doesn't exist yet and hit a FK violation on its first insert.
    await this.queue.enqueueAudit({
      auditId: created.auditId,
      orgId,
      brandName: created.brandName,
    });

    return { auditId: created.auditId, status: created.status };
  }

  async list(orgId: string, limit = 20) {
    return withTenant(this.ds, orgId, async (em) =>
      em.find(Audit, {
        order: { startedAt: "DESC" },
        take: Math.min(limit, 100),
      }),
    );
  }

  async get(orgId: string, auditId: string) {
    return withTenant(this.ds, orgId, async (em) => {
      const audit = await em.findOne(Audit, { where: { id: auditId } });
      if (!audit) {
        throw new NotFoundException(`Audit not found: ${auditId}`);
      }
      const [scores, findings, asinCount, reviewCount, brandData, asins] = await Promise.all([
        em.find(AuditScore, { where: { auditId } }),
        em.find(AuditFinding, { where: { auditId }, order: { priority: "ASC" } }),
        em.count(AuditAsin, { where: { auditId } }),
        em.count(AuditReview, { where: { auditId } }),
        em.findOne(AuditBrandData, { where: { auditId } }),
        this.ds.query(
          `SELECT asin, title, rating, review_count, bsr, bsr_category,
                  buybox_seller, image_count, bullet_count,
                  has_aplus, has_brand_story, has_video,
                  raw->>'main_image_url' AS main_image_url
           FROM audit_asins
           WHERE audit_id = $1 AND org_id = $2
           ORDER BY bsr ASC NULLS LAST
           LIMIT 200`,
          [auditId, orgId],
        ) as Promise<Array<Record<string, unknown>>>,
      ]);
      return { audit, scores, findings, asinCount, reviewCount, brandData: brandData ?? null, asins };
    });
  }

  /**
   * Observable stream of audit events (for SSE). Polls the audit_events table every
   * second for new rows since the last emitted ts. Completes when the audit reaches
   * a terminal status (complete or failed).
   */
  stream(orgId: string, auditId: string): Observable<ProgressEvent> {
    return new Observable<ProgressEvent>((subscriber) => {
      let lastTs = new Date(0).toISOString();
      let stopped = false;

      const tick = async () => {
        if (stopped) return;
        try {
          const result = await withTenant(this.ds, orgId, async (em) => {
            const events = await em
              .createQueryBuilder(AuditEvent, "e")
              .where("e.audit_id = :auditId", { auditId })
              .andWhere("e.ts > :lastTs", { lastTs })
              .orderBy("e.ts", "ASC")
              .getMany();
            const audit = await em.findOne(Audit, { where: { id: auditId } });
            return { events, audit };
          });

          if (!result.audit) {
            subscriber.error(new NotFoundException(`Audit not found: ${auditId}`));
            stopped = true;
            return;
          }

          for (const ev of result.events) {
            subscriber.next({
              ts: ev.ts.toISOString(),
              stage: ev.stage,
              message: ev.message,
              level: ev.level,
              status: result.audit.status,
            });
            lastTs = ev.ts.toISOString();
          }

          if (result.audit.status === "complete" || result.audit.status === "failed") {
            subscriber.complete();
            stopped = true;
          }
        } catch (err) {
          this.logger.error(`SSE tick failed auditId=${auditId}`, err as Error);
          subscriber.error(err);
          stopped = true;
        }
      };

      const sub = interval(1000).subscribe(() => void tick());
      // Immediate first tick so the client sees existing events without waiting 1s.
      void tick();

      return () => {
        stopped = true;
        sub.unsubscribe();
      };
    });
  }

  async submitOverrides(
    orgId: string,
    auditId: string,
    overrides: Array<{ fieldPath: string; originalValue: unknown; overrideValue: unknown }>,
  ) {
    const result = await withTenant(this.ds, orgId, async (em) => {
      const audit = await em.findOne(Audit, { where: { id: auditId } });
      if (!audit) throw new NotFoundException(`Audit not found: ${auditId}`);

      for (const o of overrides) {
        await em.insert(AuditManualOverride, {
          auditId,
          orgId,
          fieldPath: o.fieldPath,
          originalValue: o.originalValue as Record<string, unknown>,
          overrideValue: o.overrideValue as Record<string, unknown>,
        });
      }

      audit.version += 1;
      audit.status = "scoring";
      audit.finishedAt = null;
      await em.save(audit);

      await em.insert(AuditEvent, {
        auditId,
        orgId,
        stage: "rescore_queued",
        message: `User submitted ${overrides.length} overrides; re-scoring v${audit.version}`,
        level: "info",
      });

      return { auditId, version: audit.version };
    });

    // Enqueue AFTER commit — worker reads the audit row and the override rows.
    await this.queue.enqueueRescore({
      auditId: result.auditId,
      orgId,
      version: result.version,
    });
    return result;
  }
}
