import { IsOptional, IsString, MaxLength } from 'class-validator';

export class UpdateVoiceDto {
  @IsOptional()
  @IsString()
  @MaxLength(120)
  name?: string;

  @IsOptional()
  @IsString()
  @MaxLength(2000)
  characterDescription?: string | null;
}
