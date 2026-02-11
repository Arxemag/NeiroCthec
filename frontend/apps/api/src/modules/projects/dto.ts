import { ArrayNotEmpty, IsArray, IsOptional, IsString, MaxLength } from 'class-validator';

export class CreateProjectDto {
  @IsString()
  @MaxLength(120)
  title!: string;

  @IsString()
  @MaxLength(200000)
  text!: string;

  @IsString()
  @MaxLength(24)
  language!: string;

  @IsArray()
  @ArrayNotEmpty()
  voiceIds!: string[];
}

export class UpdateProjectDto {
  @IsOptional()
  @IsString()
  @MaxLength(120)
  title?: string;

  @IsOptional()
  @IsString()
  @MaxLength(200000)
  text?: string;

  @IsOptional()
  @IsString()
  @MaxLength(24)
  language?: string;

  @IsOptional()
  @IsArray()
  voiceIds?: string[];
}

