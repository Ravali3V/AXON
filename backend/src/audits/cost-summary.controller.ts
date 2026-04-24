import { Controller, Get, Query, Req } from "@nestjs/common";
import { InjectDataSource } from "@nestjs/typeorm";
import { Request } from "express";
import { DataSource } from "typeorm";
import { withTenant } from "../database/tenant-context";

/**
 * Cost dashboard — reads ai_usage_logs to surface total and per-audit LLM spend.
 * Mounted under /api/cost-summary (v1 is pre-auth — all data is the default org).
 */
@Controller("cost-summary")
export class CostSummaryController {
  constructor(@InjectDataSource() private readonly ds: DataSource) {}

  @Get()
  async summary(@Req() req: Request, @Query("days") days?: string) {
    const window = Math.max(1, Math.min(Number(days ?? 30), 365));

    return withTenant(this.ds, req.orgId, async (em) => {
      const totals: Array<{ total_usd: string; call_count: string }> = await em.query(
        `SELECT
           COALESCE(SUM(cost_usd), 0)::text AS total_usd,
           COUNT(*)::text AS call_count
         FROM ai_usage_logs
         WHERE created_at > now() - ($1 || ' days')::interval`,
        [window],
      );

      const perAudit: Array<{
        audit_id: string | null;
        total_usd: string;
        calls: string;
      }> = await em.query(
        `SELECT audit_id,
                COALESCE(SUM(cost_usd), 0)::text AS total_usd,
                COUNT(*)::text AS calls
         FROM ai_usage_logs
         WHERE created_at > now() - ($1 || ' days')::interval
         GROUP BY audit_id
         ORDER BY SUM(cost_usd) DESC
         LIMIT 50`,
        [window],
      );

      const byPurpose: Array<{ purpose: string; total_usd: string; calls: string }> =
        await em.query(
          `SELECT purpose,
                  COALESCE(SUM(cost_usd), 0)::text AS total_usd,
                  COUNT(*)::text AS calls
           FROM ai_usage_logs
           WHERE created_at > now() - ($1 || ' days')::interval
           GROUP BY purpose
           ORDER BY SUM(cost_usd) DESC`,
          [window],
        );

      const byProvider: Array<{ provider: string; total_usd: string; calls: string }> =
        await em.query(
          `SELECT provider,
                  COALESCE(SUM(cost_usd), 0)::text AS total_usd,
                  COUNT(*)::text AS calls
           FROM ai_usage_logs
           WHERE created_at > now() - ($1 || ' days')::interval
           GROUP BY provider`,
          [window],
        );

      return {
        windowDays: window,
        totalUsd: Number(totals[0]?.total_usd ?? 0),
        callCount: Number(totals[0]?.call_count ?? 0),
        perAudit: perAudit.map((r) => ({
          auditId: r.audit_id,
          totalUsd: Number(r.total_usd),
          calls: Number(r.calls),
        })),
        byPurpose: byPurpose.map((r) => ({
          purpose: r.purpose,
          totalUsd: Number(r.total_usd),
          calls: Number(r.calls),
        })),
        byProvider: byProvider.map((r) => ({
          provider: r.provider,
          totalUsd: Number(r.total_usd),
          calls: Number(r.calls),
        })),
      };
    });
  }
}
