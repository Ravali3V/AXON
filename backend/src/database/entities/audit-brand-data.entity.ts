import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  PrimaryGeneratedColumn,
} from "typeorm";

@Entity("audit_brand_data")
@Index("audit_brand_data_audit_idx", ["auditId"])
export class AuditBrandData {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "uuid", name: "audit_id" })
  auditId!: string;

  @Column({ type: "uuid", name: "org_id" })
  orgId!: string;

  @Column({ name: "brand_store_url", type: "text", nullable: true })
  brandStoreUrl!: string | null;

  @Column({ name: "brand_store_json", type: "jsonb", nullable: true })
  brandStoreJson!: Record<string, unknown> | null;

  @Column({ name: "brand_story_detected", type: "boolean", default: false })
  brandStoryDetected!: boolean;

  @Column({ name: "video_count", type: "int", default: 0 })
  videoCount!: number;

  @Column({ name: "asin_count", type: "int", default: 0 })
  asinCount!: number;

  @CreateDateColumn({ name: "scraped_at", type: "timestamptz" })
  scrapedAt!: Date;

  @Column({ name: "raw_html_gcs_path", type: "text", nullable: true })
  rawHtmlGcsPath!: string | null;
}
