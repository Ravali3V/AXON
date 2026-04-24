import { IsNotEmpty, IsString, MaxLength, MinLength } from "class-validator";

export class CreateAuditDto {
  @IsString()
  @IsNotEmpty()
  @MinLength(2)
  @MaxLength(200)
  brandName!: string;
}
