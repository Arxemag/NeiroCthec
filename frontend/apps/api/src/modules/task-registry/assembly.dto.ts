import { IsNumber, IsOptional, IsString, Max, MaxLength, Min, MinLength } from '../../lib/validators';

export type RenderAssemblyType = 'book_final_wav' | 'book_chapter_wav';

export class UpsertRenderAssemblyDto {
  @IsString()
  @MinLength(1)
  @MaxLength(200)
  assemblyId!: string;

  @IsString()
  @MinLength(1)
  @MaxLength(200)
  clientId!: string;

  @IsString()
  @MinLength(1)
  @MaxLength(200)
  bookId!: string;

  @IsString()
  @MinLength(1)
  type!: RenderAssemblyType;

  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(100000)
  chapterId?: number;

  @IsString()
  @MinLength(1)
  storageKey!: string;

  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(60_000_000)
  durationMs?: number;
}

