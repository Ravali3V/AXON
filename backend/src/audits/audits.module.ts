import { MiddlewareConsumer, Module, NestModule } from "@nestjs/common";
import { TypeOrmModule } from "@nestjs/typeorm";
import { DefaultTenantMiddleware } from "../common/default-tenant.middleware";
import { Audit } from "../database/entities/audit.entity";
import { AuditAsin } from "../database/entities/audit-asin.entity";
import { AuditBrandData } from "../database/entities/audit-brand-data.entity";
import { AuditEvent } from "../database/entities/audit-event.entity";
import { AuditFinding } from "../database/entities/audit-finding.entity";
import { AuditManualOverride } from "../database/entities/audit-manual-override.entity";
import { AuditReview } from "../database/entities/audit-review.entity";
import { AuditScore } from "../database/entities/audit-score.entity";
import { AuditsController } from "./audits.controller";
import { AuditsService } from "./audits.service";
import { CostSummaryController } from "./cost-summary.controller";
import { AUDIT_QUEUE } from "./queue/audit-queue.interface";
import { CloudTasksQueue } from "./queue/cloud-tasks.queue";
import { InProcessQueue } from "./queue/in-process.queue";

@Module({
  imports: [
    TypeOrmModule.forFeature([
      Audit,
      AuditAsin,
      AuditBrandData,
      AuditEvent,
      AuditFinding,
      AuditManualOverride,
      AuditReview,
      AuditScore,
    ]),
  ],
  controllers: [AuditsController, CostSummaryController],
  providers: [
    AuditsService,
    {
      provide: AUDIT_QUEUE,
      useClass: process.env.QUEUE_BACKEND === "cloud-tasks" ? CloudTasksQueue : InProcessQueue,
    },
  ],
})
export class AuditsModule implements NestModule {
  configure(consumer: MiddlewareConsumer): void {
    consumer.apply(DefaultTenantMiddleware).forRoutes("audits", "cost-summary");
  }
}
