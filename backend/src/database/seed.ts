/**
 * Seed script — idempotent. Runs after migrations to guarantee the default org exists.
 * Usage: pnpm run seed
 */
import "reflect-metadata";
import { AppDataSource } from "./data-source";

const DEFAULT_ORG_ID = process.env.DEFAULT_ORG_ID ?? "00000000-0000-0000-0000-000000000001";
const DEFAULT_ORG_NAME = process.env.DEFAULT_ORG_NAME ?? "AXON Internal";

async function main() {
  await AppDataSource.initialize();
  try {
    // Seeding bypasses RLS by temporarily setting the current_org GUC to match the
    // row we're about to INSERT — Postgres RLS WITH CHECK enforces this.
    await AppDataSource.transaction(async (em) => {
      await em.query(`SELECT set_config('app.current_org', $1, true)`, [DEFAULT_ORG_ID]);

      const result: Array<{ id: string; name: string }> = await em.query(
        `
          INSERT INTO "organizations" ("id", "name", "plan")
          VALUES ($1, $2, 'internal')
          ON CONFLICT ("id") DO UPDATE SET "name" = EXCLUDED."name"
          RETURNING "id", "name"
        `,
        [DEFAULT_ORG_ID, DEFAULT_ORG_NAME],
      );
      // eslint-disable-next-line no-console
      console.log(`[seed] default org: ${result[0].id} "${result[0].name}"`);
    });
  } finally {
    await AppDataSource.destroy();
  }
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error("[seed] failed", err);
  process.exit(1);
});
