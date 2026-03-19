import {
  ArrayNotEmpty,
  IsArray,
  IsNumber,
  IsObject,
  IsOptional,
  IsString,
  Max,
  MaxLength,
  Min,
  ValidateNested,
} from '../../lib/validators';
import { Type } from 'class-transformer';

/** Настройки темпа и тембра для одного спикера (narrator / male / female). */
export class SpeakerSlotDto {
  @IsOptional()
  @IsNumber()
  @Min(0.5)
  @Max(2)
  tempo?: number;

  @IsOptional()
  @IsNumber()
  @Min(-1)
  @Max(1)
  pitch?: number;
}

/** Настройки по спикерам: ключи narrator, male, female. */
export class SpeakerSettingsDto {
  @IsOptional()
  @IsObject()
  @ValidateNested()
  @Type(() => SpeakerSlotDto)
  narrator?: SpeakerSlotDto;

  @IsOptional()
  @IsObject()
  @ValidateNested()
  @Type(() => SpeakerSlotDto)
  male?: SpeakerSlotDto;

  @IsOptional()
  @IsObject()
  @ValidateNested()
  @Type(() => SpeakerSlotDto)
  female?: SpeakerSlotDto;
}

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

  @IsOptional()
  @IsObject()
  @ValidateNested()
  @Type(() => SpeakerSettingsDto)
  speakerSettings?: SpeakerSettingsDto;

  /** Сохранённый выбор голосов по ролям (narrator, male, female) для подстановки при озвучке. */
  @IsOptional()
  @IsObject()
  voiceSettings?: {
    narratorVoiceId?: string | null;
    maleVoiceId?: string | null;
    femaleVoiceId?: string | null;
  };
}

