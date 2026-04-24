import { Module } from "@nestjs/common";
import { ConfigModule } from "@nestjs/config";
import { AuditsModule } from "./audits/audits.module";
import { DatabaseModule } from "./database/database.module";
import { HealthController } from "./health.controller";

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    DatabaseModule,
    AuditsModule,
  ],
  controllers: [HealthController],
  providers: [],
})
export class AppModule {}
