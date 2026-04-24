import {
  Column,
  CreateDateColumn,
  Entity,
  Index,
  PrimaryGeneratedColumn,
} from "typeorm";

export type AiPurpose =
  | "report_narrative"
  | "strengths_weaknesses"
  | "recommendations"
  | "quick_wins"
  | "review_sentiment"
  | "listing_copy"
  | "anomaly_explain"
  | "keyword_score"
  | "chat_copilot"
  | "other";

@Entity("ai_usage_logs")
@Index("ai_usage_logs_org_created_idx", ["orgId", "createdAt"])
@Index("ai_usage_logs_audit_idx", ["auditId"])
export class AiUsageLog {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "uuid", name: "org_id" })
  orgId!: string;

  @Column({ type: "uuid", name: "audit_id", nullable: true })
  auditId!: string | null;

  @Column({ type: "text" })
  model!: string;

  @Column({ type: "text" })
  provider!: string;

  @Column({ name: "input_tokens", type: "int", default: 0 })
  inputTokens!: number;

  @Column({ name: "output_tokens", type: "int", default: 0 })
  outputTokens!: number;

  @Column({ name: "cost_usd", type: "numeric", precision: 10, scale: 6, default: 0 })
  costUsd!: string;

  @Column({ name: "latency_ms", type: "int", default: 0 })
  latencyMs!: number;

  @Column({ type: "text", default: "other" })
  purpose!: AiPurpose;

  @Column({ type: "boolean", default: true })
  success!: boolean;

  @Column({ name: "error_message", type: "text", nullable: true })
  errorMessage!: string | null;

  @CreateDateColumn({ name: "created_at", type: "timestamptz" })
  createdAt!: Date;
}
