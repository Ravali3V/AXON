import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  PrimaryGeneratedColumn,
} from "typeorm";

export type FindingType = "strength" | "weakness" | "recommendation" | "quick_win";
export type FindingSource = "rule" | "llm";

@Entity("audit_findings")
@Index("audit_findings_audit_idx", ["auditId"])
@Index("audit_findings_type_idx", ["type"])
export class AuditFinding {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "uuid", name: "audit_id" })
  auditId!: string;

  @Column({ type: "uuid", name: "org_id" })
  orgId!: string;

  @Column({ type: "text" })
  type!: FindingType;

  @Column({ type: "text" })
  section!: string;

  @Column({ type: "text" })
  text!: string;

  @Column({ type: "int", default: 3 })
  priority!: number;

  @Column({ type: "text", default: "rule" })
  source!: FindingSource;

  @CreateDateColumn({ name: "created_at", type: "timestamptz" })
  createdAt!: Date;
}
