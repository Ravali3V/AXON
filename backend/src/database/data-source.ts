import "reflect-metadata";
import { DataSource, DataSourceOptions } from "typeorm";
import { Organization } from "./entities/organization.entity";
import { User } from "./entities/user.entity";
import { Audit } from "./entities/audit.entity";
import { AuditBrandData } from "./entities/audit-brand-data.entity";
import { AuditAsin } from "./entities/audit-asin.entity";
import { AuditReview } from "./entities/audit-review.entity";
import { AuditScore } from "./entities/audit-score.entity";
import { AuditFinding } from "./entities/audit-finding.entity";
import { AuditManualOverride } from "./entities/audit-manual-override.entity";
import { AuditEvent } from "./entities/audit-event.entity";
import { AiUsageLog } from "./entities/ai-usage-log.entity";

export const entities = [
  Organization,
  User,
  Audit,
  AuditBrandData,
  AuditAsin,
  AuditReview,
  AuditScore,
  AuditFinding,
  AuditManualOverride,
  AuditEvent,
  AiUsageLog,
];

export const dataSourceOptions: DataSourceOptions = {
  type: "postgres",
  url: process.env.DATABASE_URL,
  host: process.env.DATABASE_URL ? undefined : process.env.POSTGRES_HOST ?? "localhost",
  port: process.env.DATABASE_URL ? undefined : Number(process.env.POSTGRES_PORT ?? 5432),
  username: process.env.DATABASE_URL ? undefined : process.env.POSTGRES_USER ?? "axon",
  password: process.env.DATABASE_URL
    ? undefined
    : process.env.POSTGRES_PASSWORD ?? "axon_dev_password",
  database: process.env.DATABASE_URL ? undefined : process.env.POSTGRES_DB ?? "axon",
  entities,
  migrations: [__dirname + "/migrations/*.{ts,js}"],
  migrationsTableName: "typeorm_migrations",
  synchronize: false,
  logging: process.env.DB_LOGGING === "true" ? "all" : ["error", "warn", "migration"],
};

export const AppDataSource = new DataSource(dataSourceOptions);
