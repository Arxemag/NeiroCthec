import { IsNumber, IsOptional, IsObject, IsString, Max, MaxLength, Min, MinLength } from '../../lib/validators';

export class CreateRenderTaskDto {
  @IsString()
  @MinLength(1)
  @MaxLength(200)
  taskId!: string;

  @IsString()
  @MinLength(1)
  @MaxLength(200)
  clientId!: string;

  @IsString()
  @MinLength(1)
  @MaxLength(200)
  bookId!: string;

  @IsNumber()
  @Min(0)
  lineId!: number;

  @IsOptional()
  @IsNumber()
  @Min(1)
  chapterId?: number;

  @IsOptional()
  @IsString()
  @MinLength(1)
  @MaxLength(100)
  speaker?: string;

  @IsOptional()
  @IsString()
  @MinLength(1)
  @MaxLength(50)
  lineType?: string;

  @IsOptional()
  @IsObject()
  emotion?: Record<string, unknown>;

  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(1)
  isChapterHeader?: number;

  // Сегменты при XTTS-разбиении (для правильной сортировки в Stage5Assembler)
  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(1)
  isSegment?: number;

  @IsOptional()
  @IsNumber()
  @Min(0)
  segmentIndex?: number;

  @IsOptional()
  @IsNumber()
  @Min(1)
  segmentTotal?: number;

  @IsOptional()
  @IsNumber()
  @Min(0)
  baseLineId?: number;

  @IsString()
  @MinLength(1)
  @MaxLength(100)
  engine!: string;

  // lineId is typically an integer index; we validate it as a number range (Prisma expects Int).
}

export class CompleteRenderTaskDto {
  @IsString()
  @MinLength(1)
  @MaxLength(500)
  storageKey!: string;

  @IsOptional()
  @IsNumber()
  @Min(0)
  @Max(60_000_000)
  durationMs?: number;

  @IsOptional()
  @IsNumber()
  @Min(1)
  chapterId?: number;
}

