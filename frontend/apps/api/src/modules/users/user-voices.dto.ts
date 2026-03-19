import { IsOptional, IsString, MaxLength } from '../../lib/validators';

export class CreateUserVoiceDto {
  @IsString()
  @MaxLength(120)
  name!: string;

  @IsString()
  @MaxLength(256)
  coreVoiceId!: string;

  @IsOptional()
  @IsString()
  @MaxLength(128)
  projectId?: string;
}

export class UpdateUserVoiceDto {
  @IsOptional()
  @IsString()
  @MaxLength(120)
  name?: string;

  @IsOptional()
  @IsString()
  @MaxLength(128)
  projectId?: string | null;
}
