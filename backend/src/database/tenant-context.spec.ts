/**
 * Tenant-isolation integration test.
 *
 * Runs against a real Postgres (docker-compose or CI service). Verifies that:
 *   1. A row inserted under org A is invisible when the connection runs under org B.
 *   2. A row inserted under org A is visible again when the connection runs under org A.
 *   3. With no `app.current_org` set, no rows are returned.
 *
 * Per CLAUDE.md: this test runs on every CI build and its failure blocks deploy.
 */
import { randomUUID } from "node:crypto";
import { DataSource } from "typeorm";
import { dataSourceOptions } from "./data-source";
import { withTenant } from "./tenant-context";

describe("tenant isolation", () => {
  let ds: DataSource;
  let orgA: string;
  let orgB: string;
  let auditIdA: string;

  beforeAll(async () => {
    ds = new DataSource(dataSourceOptions);
    await ds.initialize();

    orgA = randomUUID();
    orgB = randomUUID();

    // Both orgs must exist — seed them with RLS set to their own UUID.
    for (const id of [orgA, orgB]) {
      await withTenant(ds, id, async (em) => {
        await em.query(
          `INSERT INTO "organizations" ("id", "name") VALUES ($1, $2)
           ON CONFLICT ("id") DO NOTHING`,
          [id, `Test Org ${id.slice(0, 8)}`],
        );
      });
    }

    auditIdA = await withTenant(ds, orgA, async (em) => {
      const [row]: Array<{ id: string }> = await em.query(
        `INSERT INTO "audits" ("org_id", "brand_name") VALUES ($1, $2) RETURNING "id"`,
        [orgA, "test-brand-a"],
      );
      return row.id;
    });
  });

  afterAll(async () => {
    // Clean up both orgs (cascade deletes their audits).
    for (const id of [orgA, orgB]) {
      await withTenant(ds, id, async (em) => {
        await em.query(`DELETE FROM "organizations" WHERE "id" = $1`, [id]);
      });
    }
    await ds.destroy();
  });

  it("returns the row to its owner org", async () => {
    const rows = await withTenant(ds, orgA, async (em) =>
      em.query(`SELECT "id" FROM "audits" WHERE "id" = $1`, [auditIdA]),
    );
    expect(rows).toHaveLength(1);
  });

  it("hides the row from a different org", async () => {
    const rows = await withTenant(ds, orgB, async (em) =>
      em.query(`SELECT "id" FROM "audits" WHERE "id" = $1`, [auditIdA]),
    );
    expect(rows).toHaveLength(0);
  });

  it("returns zero rows when no tenant is set", async () => {
    // Deliberately bypass withTenant — raw query with no GUC.
    const rows = await ds.query(`SELECT "id" FROM "audits" WHERE "id" = $1`, [auditIdA]);
    expect(rows).toHaveLength(0);
  });

  it("rejects a WITH CHECK violation (insert into wrong org)", async () => {
    await expect(
      withTenant(ds, orgA, async (em) =>
        em.query(
          `INSERT INTO "audits" ("org_id", "brand_name") VALUES ($1, $2)`,
          [orgB, "should-fail"],
        ),
      ),
    ).rejects.toThrow(/row-level security/i);
  });
});
