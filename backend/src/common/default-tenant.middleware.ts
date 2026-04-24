import { Injectable, NestMiddleware } from "@nestjs/common";
import { NextFunction, Request, Response } from "express";

/**
 * v1 pre-auth middleware: every request gets attributed to the default seeded org.
 *
 * When Custom JWT auth lands in v1.1, this middleware is replaced by one that extracts
 * `org_id` from the verified JWT. The downstream code (controllers, services) doesn't
 * change — it always reads `req.orgId`.
 *
 * The `req.orgId` property is typed via `src/types/express.d.ts`.
 */
@Injectable()
export class DefaultTenantMiddleware implements NestMiddleware {
  private readonly defaultOrgId: string;

  constructor() {
    this.defaultOrgId =
      process.env.DEFAULT_ORG_ID ?? "00000000-0000-0000-0000-000000000001";
  }

  use(req: Request, _res: Response, next: NextFunction): void {
    req.orgId = this.defaultOrgId;
    next();
  }
}
