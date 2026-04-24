import { Column, Entity, Index, PrimaryGeneratedColumn } from "typeorm";

export type ScoreStatus = "scored" | "na" | "warning";

@Entity("audit_scores")
@Index("audit_scores_audit_idx", ["auditId"])
@Index("audit_scores_audit_section_criterion_uk", ["auditId", "section", "criterion"], {
  unique: true,
})
export class AuditScore {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "uuid", name: "audit_id" })
  auditId!: string;

  @Column({ type: "uuid", name: "org_id" })
  orgId!: string;

  @Column({ type: "text" })
  section!: string;

  @Column({ type: "text" })
  criterion!: string;

  @Column({ name: "points_earned", type: "numeric", precision: 5, scale: 2 })
  pointsEarned!: string;

  @Column({ name: "points_possible", type: "numeric", precision: 5, scale: 2 })
  pointsPossible!: string;

  @Column({ type: "text", default: "scored" })
  status!: ScoreStatus;

  @Column({ type: "jsonb", nullable: true })
  evidence!: Record<string, unknown> | null;
}
