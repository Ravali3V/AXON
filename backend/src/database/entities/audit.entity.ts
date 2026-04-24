import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  PrimaryGeneratedColumn,
} from "typeorm";

export type AuditStatus =
  | "queued"
  | "resolving"
  | "scraping"
  | "scoring"
  | "enriching"
  | "rendering"
  | "complete"
  | "failed";

export type AuditGrade = "A" | "B" | "C" | "D" | "F";

@Entity("audits")
@Index("audits_org_started_idx", ["orgId", "startedAt"])
export class Audit {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "uuid", name: "org_id" })
  orgId!: string;

  @Column({ type: "text", name: "brand_name" })
  brandName!: string;

  @Column({ type: "text", default: "queued" })
  status!: AuditStatus;

  @CreateDateColumn({ name: "started_at", type: "timestamptz" })
  startedAt!: Date;

  @Column({ name: "finished_at", type: "timestamptz", nullable: true })
  finishedAt!: Date | null;

  @Column({ name: "score_total", type: "int", nullable: true })
  scoreTotal!: number | null;

  @Column({ name: "score_possible", type: "int", nullable: true })
  scorePossible!: number | null;

  @Column({ type: "text", nullable: true })
  grade!: AuditGrade | null;

  @Column({ name: "report_pdf_gcs_path", type: "text", nullable: true })
  reportPdfGcsPath!: string | null;

  @Column({ type: "int", default: 1 })
  version!: number;

  @Column({ name: "error_message", type: "text", nullable: true })
  errorMessage!: string | null;
}
