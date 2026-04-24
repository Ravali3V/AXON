import { MigrationInterface, QueryRunner } from "typeorm";

/**
 * Initial AXON schema — Brand Audit Tier 1.
 *
 * Creates all 11 tables from the approved plan, plus:
 *   - citext extension (case-insensitive email)
 *   - pgcrypto extension (gen_random_uuid)
 *   - An app-level role `axon_app` that the backend connects as (RLS is enforced).
 *   - RLS policies on every tenant-scoped table using
 *     `current_setting('app.current_org', true)::uuid`.
 *   - A default seeded organization (so v1 pre-auth has something to attribute to).
 */
export class InitialSchema1713700000000 implements MigrationInterface {
  name = "InitialSchema1713700000000";

  public async up(queryRunner: QueryRunner): Promise<void> {
    // -------- Extensions --------
    await queryRunner.query(`CREATE EXTENSION IF NOT EXISTS "pgcrypto"`);
    await queryRunner.query(`CREATE EXTENSION IF NOT EXISTS "citext"`);

    // -------- organizations --------
    await queryRunner.query(`
      CREATE TABLE "organizations" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "name" text NOT NULL,
        "plan" text NULL,
        "created_at" timestamptz NOT NULL DEFAULT now()
      )
    `);

    // -------- users --------
    await queryRunner.query(`
      CREATE TABLE "users" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "org_id" uuid NOT NULL REFERENCES "organizations"("id") ON DELETE CASCADE,
        "email" citext NOT NULL,
        "password_hash" text NULL,
        "role" text NOT NULL DEFAULT 'member',
        "created_at" timestamptz NOT NULL DEFAULT now()
      )
    `);
    await queryRunner.query(
      `CREATE UNIQUE INDEX "users_org_email_uk" ON "users" ("org_id", "email")`,
    );

    // -------- audits --------
    await queryRunner.query(`
      CREATE TABLE "audits" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "org_id" uuid NOT NULL REFERENCES "organizations"("id") ON DELETE CASCADE,
        "brand_name" text NOT NULL,
        "status" text NOT NULL DEFAULT 'queued',
        "started_at" timestamptz NOT NULL DEFAULT now(),
        "finished_at" timestamptz NULL,
        "score_total" int NULL,
        "score_possible" int NULL,
        "grade" text NULL,
        "report_pdf_gcs_path" text NULL,
        "version" int NOT NULL DEFAULT 1,
        "error_message" text NULL,
        CONSTRAINT "audits_status_chk" CHECK (
          "status" IN ('queued','resolving','scraping','scoring','enriching','rendering','complete','failed')
        ),
        CONSTRAINT "audits_grade_chk" CHECK (
          "grade" IS NULL OR "grade" IN ('A','B','C','D','F')
        )
      )
    `);
    await queryRunner.query(
      `CREATE INDEX "audits_org_started_idx" ON "audits" ("org_id", "started_at" DESC)`,
    );

    // -------- audit_brand_data --------
    await queryRunner.query(`
      CREATE TABLE "audit_brand_data" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "audit_id" uuid NOT NULL REFERENCES "audits"("id") ON DELETE CASCADE,
        "org_id" uuid NOT NULL REFERENCES "organizations"("id") ON DELETE CASCADE,
        "brand_store_url" text NULL,
        "brand_store_json" jsonb NULL,
        "brand_story_detected" boolean NOT NULL DEFAULT false,
        "video_count" int NOT NULL DEFAULT 0,
        "asin_count" int NOT NULL DEFAULT 0,
        "scraped_at" timestamptz NOT NULL DEFAULT now(),
        "raw_html_gcs_path" text NULL
      )
    `);
    await queryRunner.query(
      `CREATE INDEX "audit_brand_data_audit_idx" ON "audit_brand_data" ("audit_id")`,
    );

    // -------- audit_asins --------
    await queryRunner.query(`
      CREATE TABLE "audit_asins" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "audit_id" uuid NOT NULL REFERENCES "audits"("id") ON DELETE CASCADE,
        "org_id" uuid NOT NULL REFERENCES "organizations"("id") ON DELETE CASCADE,
        "asin" text NOT NULL,
        "title" text NULL,
        "price" numeric(10,2) NULL,
        "bsr" int NULL,
        "bsr_category" text NULL,
        "rating" numeric(2,1) NULL,
        "review_count" int NULL,
        "image_count" int NOT NULL DEFAULT 0,
        "bullet_count" int NOT NULL DEFAULT 0,
        "has_aplus" boolean NOT NULL DEFAULT false,
        "has_brand_story" boolean NOT NULL DEFAULT false,
        "has_video" boolean NOT NULL DEFAULT false,
        "buybox_seller" text NULL,
        "variation_parent_asin" text NULL,
        "raw" jsonb NULL
      )
    `);
    await queryRunner.query(
      `CREATE INDEX "audit_asins_audit_idx" ON "audit_asins" ("audit_id")`,
    );
    await queryRunner.query(
      `CREATE UNIQUE INDEX "audit_asins_audit_asin_uk" ON "audit_asins" ("audit_id", "asin")`,
    );

    // -------- audit_reviews --------
    await queryRunner.query(`
      CREATE TABLE "audit_reviews" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "audit_id" uuid NOT NULL REFERENCES "audits"("id") ON DELETE CASCADE,
        "org_id" uuid NOT NULL REFERENCES "organizations"("id") ON DELETE CASCADE,
        "asin" text NOT NULL,
        "review_id" text NULL,
        "rating" int NULL,
        "verified" boolean NOT NULL DEFAULT false,
        "helpful_votes" int NOT NULL DEFAULT 0,
        "title" text NULL,
        "body" text NULL,
        "sentiment" text NULL,
        "themes" text[] NOT NULL DEFAULT '{}',
        CONSTRAINT "audit_reviews_sentiment_chk" CHECK (
          "sentiment" IS NULL OR "sentiment" IN ('positive','neutral','negative')
        ),
        CONSTRAINT "audit_reviews_rating_chk" CHECK (
          "rating" IS NULL OR ("rating" BETWEEN 1 AND 5)
        )
      )
    `);
    await queryRunner.query(
      `CREATE INDEX "audit_reviews_audit_idx" ON "audit_reviews" ("audit_id")`,
    );
    await queryRunner.query(
      `CREATE INDEX "audit_reviews_audit_asin_idx" ON "audit_reviews" ("audit_id", "asin")`,
    );

    // -------- audit_scores --------
    await queryRunner.query(`
      CREATE TABLE "audit_scores" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "audit_id" uuid NOT NULL REFERENCES "audits"("id") ON DELETE CASCADE,
        "org_id" uuid NOT NULL REFERENCES "organizations"("id") ON DELETE CASCADE,
        "section" text NOT NULL,
        "criterion" text NOT NULL,
        "points_earned" numeric(5,2) NOT NULL,
        "points_possible" numeric(5,2) NOT NULL,
        "status" text NOT NULL DEFAULT 'scored',
        "evidence" jsonb NULL,
        CONSTRAINT "audit_scores_status_chk" CHECK ("status" IN ('scored','na','warning'))
      )
    `);
    await queryRunner.query(
      `CREATE INDEX "audit_scores_audit_idx" ON "audit_scores" ("audit_id")`,
    );
    await queryRunner.query(
      `CREATE UNIQUE INDEX "audit_scores_audit_section_criterion_uk"
       ON "audit_scores" ("audit_id", "section", "criterion")`,
    );

    // -------- audit_findings --------
    await queryRunner.query(`
      CREATE TABLE "audit_findings" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "audit_id" uuid NOT NULL REFERENCES "audits"("id") ON DELETE CASCADE,
        "org_id" uuid NOT NULL REFERENCES "organizations"("id") ON DELETE CASCADE,
        "type" text NOT NULL,
        "section" text NOT NULL,
        "text" text NOT NULL,
        "priority" int NOT NULL DEFAULT 3,
        "source" text NOT NULL DEFAULT 'rule',
        "created_at" timestamptz NOT NULL DEFAULT now(),
        CONSTRAINT "audit_findings_type_chk" CHECK (
          "type" IN ('strength','weakness','recommendation','quick_win')
        ),
        CONSTRAINT "audit_findings_source_chk" CHECK ("source" IN ('rule','llm'))
      )
    `);
    await queryRunner.query(
      `CREATE INDEX "audit_findings_audit_idx" ON "audit_findings" ("audit_id")`,
    );
    await queryRunner.query(
      `CREATE INDEX "audit_findings_type_idx" ON "audit_findings" ("type")`,
    );

    // -------- audit_manual_overrides --------
    await queryRunner.query(`
      CREATE TABLE "audit_manual_overrides" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "audit_id" uuid NOT NULL REFERENCES "audits"("id") ON DELETE CASCADE,
        "org_id" uuid NOT NULL REFERENCES "organizations"("id") ON DELETE CASCADE,
        "field_path" text NOT NULL,
        "original_value" jsonb NULL,
        "override_value" jsonb NOT NULL,
        "set_by" uuid NULL REFERENCES "users"("id") ON DELETE SET NULL,
        "set_at" timestamptz NOT NULL DEFAULT now()
      )
    `);
    await queryRunner.query(
      `CREATE INDEX "audit_overrides_audit_idx" ON "audit_manual_overrides" ("audit_id")`,
    );

    // -------- audit_events --------
    await queryRunner.query(`
      CREATE TABLE "audit_events" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "audit_id" uuid NOT NULL REFERENCES "audits"("id") ON DELETE CASCADE,
        "org_id" uuid NOT NULL REFERENCES "organizations"("id") ON DELETE CASCADE,
        "ts" timestamptz NOT NULL DEFAULT now(),
        "stage" text NOT NULL,
        "message" text NOT NULL,
        "level" text NOT NULL DEFAULT 'info',
        CONSTRAINT "audit_events_level_chk" CHECK ("level" IN ('info','warn','error'))
      )
    `);
    await queryRunner.query(
      `CREATE INDEX "audit_events_audit_ts_idx" ON "audit_events" ("audit_id", "ts")`,
    );

    // -------- ai_usage_logs --------
    await queryRunner.query(`
      CREATE TABLE "ai_usage_logs" (
        "id" uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        "org_id" uuid NOT NULL REFERENCES "organizations"("id") ON DELETE CASCADE,
        "audit_id" uuid NULL REFERENCES "audits"("id") ON DELETE SET NULL,
        "model" text NOT NULL,
        "provider" text NOT NULL,
        "input_tokens" int NOT NULL DEFAULT 0,
        "output_tokens" int NOT NULL DEFAULT 0,
        "cost_usd" numeric(10,6) NOT NULL DEFAULT 0,
        "latency_ms" int NOT NULL DEFAULT 0,
        "purpose" text NOT NULL DEFAULT 'other',
        "success" boolean NOT NULL DEFAULT true,
        "error_message" text NULL,
        "created_at" timestamptz NOT NULL DEFAULT now()
      )
    `);
    await queryRunner.query(
      `CREATE INDEX "ai_usage_logs_org_created_idx" ON "ai_usage_logs" ("org_id", "created_at" DESC)`,
    );
    await queryRunner.query(
      `CREATE INDEX "ai_usage_logs_audit_idx" ON "ai_usage_logs" ("audit_id")`,
    );

    // -------- RLS --------
    // Every tenant-scoped table enables + forces RLS, with a policy that reads
    // the tenant from the `app.current_org` GUC set by the backend per-request.
    const tenantTables = [
      "organizations",
      "users",
      "audits",
      "audit_brand_data",
      "audit_asins",
      "audit_reviews",
      "audit_scores",
      "audit_findings",
      "audit_manual_overrides",
      "audit_events",
      "ai_usage_logs",
    ];

    for (const t of tenantTables) {
      const orgColumn = t === "organizations" ? "id" : "org_id";
      await queryRunner.query(`ALTER TABLE "${t}" ENABLE ROW LEVEL SECURITY`);
      await queryRunner.query(`ALTER TABLE "${t}" FORCE ROW LEVEL SECURITY`);
      await queryRunner.query(`
        CREATE POLICY "${t}_tenant_isolation" ON "${t}"
        USING (
          current_setting('app.current_org', true) IS NOT NULL
          AND current_setting('app.current_org', true) <> ''
          AND "${orgColumn}" = current_setting('app.current_org', true)::uuid
        )
        WITH CHECK (
          current_setting('app.current_org', true) IS NOT NULL
          AND current_setting('app.current_org', true) <> ''
          AND "${orgColumn}" = current_setting('app.current_org', true)::uuid
        )
      `);
    }

    // -------- Default org --------
    // Seeded with a stable UUID so v1 (pre-auth) can attribute all audits here.
    // Set app.current_org LOCAL so the INSERT passes the RLS WITH CHECK we just enabled.
    await queryRunner.query(
      `SELECT set_config('app.current_org', '00000000-0000-0000-0000-000000000001', true)`,
    );
    await queryRunner.query(`
      INSERT INTO "organizations" ("id", "name", "plan")
      VALUES ('00000000-0000-0000-0000-000000000001', 'AXON Internal', 'internal')
      ON CONFLICT ("id") DO NOTHING
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    // Drop in reverse dependency order.
    const drops = [
      "ai_usage_logs",
      "audit_events",
      "audit_manual_overrides",
      "audit_findings",
      "audit_scores",
      "audit_reviews",
      "audit_asins",
      "audit_brand_data",
      "audits",
      "users",
      "organizations",
    ];
    for (const t of drops) {
      await queryRunner.query(`DROP TABLE IF EXISTS "${t}" CASCADE`);
    }
  }
}
