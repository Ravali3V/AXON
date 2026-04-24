// Global Express request augmentation — adds tenant fields that our middleware
// stamps onto every request.
//
// We use `declare global namespace Express` (from @types/express) rather than
// `declare module "express-serve-static-core"` because pnpm's strict hoisting
// hides the latter from TypeScript resolution.

export {};

declare global {
  namespace Express {
    interface Request {
      /** UUID of the tenant making the request. Set by DefaultTenantMiddleware. */
      orgId: string;
    }
  }
}
