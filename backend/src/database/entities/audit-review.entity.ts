import { Column, Entity, Index, PrimaryGeneratedColumn } from "typeorm";

export type ReviewSentiment = "positive" | "neutral" | "negative" | null;

@Entity("audit_reviews")
@Index("audit_reviews_audit_idx", ["auditId"])
@Index("audit_reviews_audit_asin_idx", ["auditId", "asin"])
export class AuditReview {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "uuid", name: "audit_id" })
  auditId!: string;

  @Column({ type: "uuid", name: "org_id" })
  orgId!: string;

  @Column({ type: "text" })
  asin!: string;

  @Column({ name: "review_id", type: "text", nullable: true })
  reviewId!: string | null;

  @Column({ type: "int", nullable: true })
  rating!: number | null;

  @Column({ type: "boolean", default: false })
  verified!: boolean;

  @Column({ name: "helpful_votes", type: "int", default: 0 })
  helpfulVotes!: number;

  @Column({ type: "text", nullable: true })
  title!: string | null;

  @Column({ type: "text", nullable: true })
  body!: string | null;

  @Column({ type: "text", nullable: true })
  sentiment!: ReviewSentiment;

  @Column({ type: "text", array: true, default: () => "'{}'" })
  themes!: string[];
}
