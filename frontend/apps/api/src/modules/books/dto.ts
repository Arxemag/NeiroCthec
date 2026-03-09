import { IsNumber, IsOptional, IsString, MaxLength, Min } from '../../lib/validators';

export class CreateBookFromProjectDto {
  @IsString()
  appBookId!: string;

  /** Идентификатор пользователя в App API (X-User-Id при загрузке). Если не передан, используется userId из JWT. */
  @IsOptional()
  @IsString()
  appUserId?: string;
}

export class UpdateBookDto {
  @IsOptional()
  @IsString()
  @MaxLength(300)
  title?: string;

  @IsOptional()
  @IsString()
  @MaxLength(5000)
  description?: string | null;

  @IsOptional()
  @IsString()
  @MaxLength(200)
  author?: string | null;

  @IsOptional()
  @IsString()
  @MaxLength(100)
  genre?: string | null;

  @IsOptional()
  @IsString()
  seriesId?: string | null;

  @IsOptional()
  @IsNumber()
  @Min(1)
  seriesOrder?: number | null;
}

export class CreateSeriesDto {
  @IsString()
  @MaxLength(200)
  name!: string;
}
