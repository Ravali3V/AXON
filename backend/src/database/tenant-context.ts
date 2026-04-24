import { DataSource, EntityManager } from "typeorm";

/**
 * Runs a function inside a transaction with `app.current_org` set for the duration.
 * This is the ONLY way backend code is allowed to read tenant-scoped tables —
 * Postgres RLS refuses rows otherwise.
 *
 * In v1 (pre-auth) the caller passes the default org UUID from `DEFAULT_ORG_ID`.
 * When JWT auth lands, middleware will extract the org from the token and call this.
 */
export async function withTenant<T>(
  dataSource: DataSource,
  orgId: string,
  fn: (em: EntityManager) => Promise<T>,
): Promise<T> {
  if (!isUuid(orgId)) {
    throw new Error(`withTenant: invalid org UUID: ${orgId}`);
  }

  return dataSource.transaction(async (em) => {
    // `set_config` is the SQL-visible equivalent of SET LOCAL, parameter-safe.
    // true => local to this transaction only.
    await em.query(`SELECT set_config('app.current_org', $1, true)`, [orgId]);
    return fn(em);
  });
}

function isUuid(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
  );
}
