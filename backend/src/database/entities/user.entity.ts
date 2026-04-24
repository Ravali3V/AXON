import { Column, CreateDateColumn, Entity, Index, PrimaryGeneratedColumn } from "typeorm";

export type UserRole = "admin" | "member";

@Entity("users")
@Index("users_org_email_uk", ["orgId", "email"], { unique: true })
export class User {
  @PrimaryGeneratedColumn("uuid")
  id!: string;

  @Column({ type: "uuid", name: "org_id" })
  orgId!: string;

  @Column({ type: "citext" })
  email!: string;

  // Nullable in v1 — no login yet. bcrypt hash when auth lands.
  @Column({ type: "text", name: "password_hash", nullable: true })
  passwordHash!: string | null;

  @Column({ type: "text", default: "member" })
  role!: UserRole;

  @CreateDateColumn({ name: "created_at", type: "timestamptz" })
  createdAt!: Date;
}
