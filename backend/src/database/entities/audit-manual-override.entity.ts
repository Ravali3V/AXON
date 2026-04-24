import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  PrimaryGeneratedColumn,
} from "typeorm";

@Entity("audit_manual_overrides")
@Index("audit_overrides_audit_idx", ["auditId"])
export class AuditManualOverride {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "uuid", name: "audit_id" })
  auditId!: string;

  @Column({ type: "uuid", name: "org_id" })
  orgId!: string;

  // e.g. "asin.B00XYZ.imageCount" or "brand.storeExists"
  @Column({ name: "field_path", type: "text" })
  fieldPath!: string;

  @Column({ name: "original_value", type: "jsonb", nullable: true })
  originalValue!: unknown;

  @Column({ name: "override_value", type: "jsonb" })
  overrideValue!: unknown;

  @Column({ name: "set_by", type: "uuid", nullable: true })
  setBy!: string | null;

  @CreateDateColumn({ name: "set_at", type: "timestamptz" })
  setAt!: Date;
}
