import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  PrimaryGeneratedColumn,
} from "typeorm";

export type EventLevel = "info" | "warn" | "error";

@Entity("audit_events")
@Index("audit_events_audit_ts_idx", ["auditId", "ts"])
export class AuditEvent {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "uuid", name: "audit_id" })
  auditId!: string;

  @Column({ type: "uuid", name: "org_id" })
  orgId!: string;

  @CreateDateColumn({ type: "timestamptz" })
  ts!: Date;

  @Column({ type: "text" })
  stage!: string;

  @Column({ type: "text" })
  message!: string;

  @Column({ type: "text", default: "info" })
  level!: EventLevel;
}
