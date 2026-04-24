import * as fs from "fs";
import * as path from "path";
import {
  Body,
  Controller,
  Get,
  HttpCode,
  HttpStatus,
  NotFoundException,
  Param,
  ParseUUIDPipe,
  Post,
  Req,
  Res,
  Sse,
} from "@nestjs/common";
import { Request, Response } from "express";
import { map, Observable } from "rxjs";
import { Storage } from "@google-cloud/storage";
import { AuditsService, ProgressEvent } from "./audits.service";
import { CreateAuditDto } from "./dto/create-audit.dto";

@Controller("audits")
export class AuditsController {
  private readonly storage = new Storage();
  private readonly bucket = process.env.GCS_REPORTS_BUCKET ?? "axon-reports";

  constructor(private readonly service: AuditsService) {}

  @Post()
  @HttpCode(HttpStatus.ACCEPTED)
  async create(@Req() req: Request, @Body() dto: CreateAuditDto) {
    return this.service.create(req.orgId, dto);
  }

  @Get()
  async list(@Req() req: Request) {
    return this.service.list(req.orgId);
  }

  @Get(":id")
  async get(@Req() req: Request, @Param("id", new ParseUUIDPipe()) id: string) {
    return this.service.get(req.orgId, id);
  }

  @Sse(":id/events")
  stream(
    @Req() req: Request,
    @Param("id", new ParseUUIDPipe()) id: string,
  ): Observable<MessageEvent> {
    return this.service.stream(req.orgId, id).pipe(
      map((ev: ProgressEvent): MessageEvent => ({
        data: JSON.stringify(ev),
        type: "progress",
      } as MessageEvent)),
    );
  }

  /**
   * Stream the PDF directly as application/pdf.
   * Dev: reads the local file written by the worker.
   * Prod: downloads from GCS and pipes to the client.
   */
  @Get(":id/pdf")
  async pdf(
    @Req() req: Request,
    @Param("id", new ParseUUIDPipe()) id: string,
    @Res() res: Response,
  ): Promise<void> {
    const { audit } = await this.service.get(req.orgId, id);

    if (!audit.reportPdfGcsPath) {
      res.status(HttpStatus.NOT_FOUND).json({ message: "Report PDF not yet generated for this audit." });
      return;
    }

    const brandSlug = (audit.brandName ?? "audit")
      .replace(/[^a-z0-9]/gi, "-")
      .replace(/-+/g, "-")
      .toLowerCase();
    const fileName = `${brandSlug}-brand-audit.pdf`;

    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Disposition", `attachment; filename="${fileName}"`);

    // Dev mode: file:// path written by worker/src/pdf/storage.py
    if (audit.reportPdfGcsPath.startsWith("file://")) {
      let localPath = decodeURIComponent(
        audit.reportPdfGcsPath.replace(/^file:\/\//, ""),
      );
      // On Windows, as_posix() produces "D:/..." — strip any leading slash before drive letter.
      if (/^\/[A-Za-z]:/.test(localPath)) {
        localPath = localPath.slice(1);
      }
      localPath = path.normalize(localPath);

      if (!fs.existsSync(localPath)) {
        res.status(HttpStatus.NOT_FOUND).json({ message: `PDF file not found at ${localPath}` });
        return;
      }
      fs.createReadStream(localPath).pipe(res);
      return;
    }

    // Prod: GCS
    const match = /^gs:\/\/([^/]+)\/(.+)$/.exec(audit.reportPdfGcsPath);
    if (!match) {
      res.status(HttpStatus.INTERNAL_SERVER_ERROR).json({ message: "Malformed PDF path on audit record." });
      return;
    }
    const [, bucket, objectPath] = match;
    if (bucket !== this.bucket) {
      res.status(HttpStatus.INTERNAL_SERVER_ERROR).json({ message: "Report PDF not in expected bucket." });
      return;
    }

    const file = this.storage.bucket(bucket).file(objectPath);
    const [buffer] = await file.download();
    res.send(buffer);
  }

  @Post(":id/overrides")
  @HttpCode(HttpStatus.ACCEPTED)
  async submitOverrides(
    @Req() req: Request,
    @Param("id", new ParseUUIDPipe()) id: string,
    @Body()
    body: {
      overrides: Array<{ fieldPath: string; originalValue: unknown; overrideValue: unknown }>;
    },
  ) {
    return this.service.submitOverrides(req.orgId, id, body.overrides ?? []);
  }
}
