import { MigrationInterface, QueryRunner } from "typeorm";

export class UpdateGradeConstraint1745416000000 implements MigrationInterface {
  public async up(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      ALTER TABLE "audits"
        DROP CONSTRAINT IF EXISTS "audits_grade_chk"
    `);
    // Null out any rows that still carry old letter grades so the new
    // constraint can be added cleanly. Dev data only — no prod rows yet.
    await queryRunner.query(`
      UPDATE "audits"
        SET "grade" = NULL
        WHERE "grade" NOT IN ('Thriving','Growing','Building','Emerging','Untapped')
    `);
    await queryRunner.query(`
      ALTER TABLE "audits"
        ADD CONSTRAINT "audits_grade_chk"
          CHECK ("grade" IS NULL OR "grade" IN ('Thriving','Growing','Building','Emerging','Untapped'))
    `);
  }

  public async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query(`
      ALTER TABLE "audits"
        DROP CONSTRAINT IF EXISTS "audits_grade_chk"
    `);
    await queryRunner.query(`
      ALTER TABLE "audits"
        ADD CONSTRAINT "audits_grade_chk"
          CHECK ("grade" IS NULL OR "grade" IN ('A','B','C','D','F'))
    `);
  }
}
