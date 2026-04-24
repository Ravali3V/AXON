import { Column, Entity, Index, PrimaryGeneratedColumn } from "typeorm";

@Entity("audit_asins")
@Index("audit_asins_audit_idx", ["auditId"])
@Index("audit_asins_audit_asin_uk", ["auditId", "asin"], { unique: true })
export class AuditAsin {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "uuid", name: "audit_id" })
  auditId!: string;

  @Column({ type: "uuid", name: "org_id" })
  orgId!: string;

  @Column({ type: "text" })
  asin!: string;

  @Column({ type: "text", nullable: true })
  title!: string | null;

  @Column({ type: "numeric", precision: 10, scale: 2, nullable: true })
  price!: string | null;

  @Column({ type: "int", nullable: true })
  bsr!: number | null;

  @Column({ name: "bsr_category", type: "text", nullable: true })
  bsrCategory!: string | null;

  @Column({ type: "numeric", precision: 2, scale: 1, nullable: true })
  rating!: string | null;

  @Column({ name: "review_count", type: "int", nullable: true })
  reviewCount!: number | null;

  @Column({ name: "image_count", type: "int", default: 0 })
  imageCount!: number;

  @Column({ name: "bullet_count", type: "int", default: 0 })
  bulletCount!: number;

  @Column({ name: "has_aplus", type: "boolean", default: false })
  hasAplus!: boolean;

  @Column({ name: "has_brand_story", type: "boolean", default: false })
  hasBrandStory!: boolean;

  @Column({ name: "has_video", type: "boolean", default: false })
  hasVideo!: boolean;

  @Column({ name: "buybox_seller", type: "text", nullable: true })
  buyboxSeller!: string | null;

  @Column({ name: "variation_parent_asin", type: "text", nullable: true })
  variationParentAsin!: string | null;

  @Column({ type: "jsonb", nullable: true })
  raw!: Record<string, unknown> | null;
}
