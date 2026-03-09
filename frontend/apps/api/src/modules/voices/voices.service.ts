import {
  BadGatewayException,
  ConflictException,
  HttpException,
  HttpStatus,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import type { VoiceGender, VoiceRole } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import type { UpdateVoiceDto } from './dto';

@Injectable()
export class VoicesService {
  constructor(private readonly prisma: PrismaService) {}

  async list(filters: { language?: string; gender?: string; style?: string; role?: string }) {
    const where: {
      isActive: boolean;
      provider?: { not: string };
      language?: string;
      gender?: VoiceGender;
      style?: string;
      role?: VoiceRole;
    } = {
      isActive: true,
      provider: { not: 'stub' }, // не отдаём заглушки из сида (Анна, Максим, Alex)
    };
    if (filters.language != null && filters.language !== '') where.language = filters.language;
    if (filters.gender != null && filters.gender !== '') where.gender = filters.gender as VoiceGender;
    if (filters.style != null && filters.style !== '') where.style = filters.style;
    if (filters.role != null && filters.role !== '') where.role = filters.role as VoiceRole;

    return this.prisma.voice.findMany({
      where,
      orderBy: [{ role: 'asc' }, { language: 'asc' }, { name: 'asc' }],
    });
  }

  /**
   * Прокси к Core: список голосов (встроенные + свои по X-User-Id). Один источник правды — Core.
   */
  async listFromCore(userId: string): Promise<Array<{ id: string; name: string; role?: string; sample_url?: string }>> {
    const base = process.env.CORE_API_URL ?? process.env.APP_API_URL ?? '';
    if (!base) {
      throw new HttpException('Core API not configured: set CORE_API_URL or APP_API_URL', HttpStatus.NOT_IMPLEMENTED);
    }
    const url = `${base.replace(/\/$/, '')}/voices`;
    // #region agent log
    try {
      fetch('http://127.0.0.1:7653/ingest/197dff00-57dd-45ca-809c-c08d9512ccf4', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '9376b5' },
        body: JSON.stringify({
          sessionId: '9376b5',
          hypothesisId: 'voices-nest-core',
          location: 'voices.service.ts:listFromCore',
          message: 'Nest calling Core for voices',
          data: { url, userId: userId?.slice(0, 8) },
          timestamp: Date.now(),
        }),
      }).catch(() => {});
    } catch (_) {}
    // #endregion
    const res = await fetch(url, { headers: { 'X-User-Id': userId } });
    const text = await res.text();
    // #region agent log
    try {
      fetch('http://127.0.0.1:7653/ingest/197dff00-57dd-45ca-809c-c08d9512ccf4', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Debug-Session-Id': '9376b5' },
        body: JSON.stringify({
          sessionId: '9376b5',
          hypothesisId: 'voices-nest-core',
          location: 'voices.service.ts:listFromCore',
          message: res.ok ? 'Core voices response' : 'Core voices failed',
          data: { status: res.status, ok: res.ok, bodyPreview: text?.slice(0, 200) },
          timestamp: Date.now(),
        }),
      }).catch(() => {});
    } catch (_) {}
    // #endregion
    if (!res.ok) {
      throw new BadGatewayException(`Core voices failed: ${res.status} ${text}`);
    }
    return JSON.parse(text);
  }

  async getById(id: string) {
    const v = await this.prisma.voice.findUnique({ where: { id } });
    if (!v || !v.isActive) throw new NotFoundException('Voice not found');
    return v;
  }

  async update(id: string, dto: UpdateVoiceDto) {
    await this.getById(id);
    const data: { name?: string; characterDescription?: string | null } = {};
    if (dto.name != null) data.name = dto.name;
    if (dto.characterDescription !== undefined) data.characterDescription = dto.characterDescription;
    if (Object.keys(data).length === 0) return this.getById(id);
    return this.prisma.voice.update({
      where: { id },
      data,
    });
  }

  async delete(id: string) {
    await this.getById(id);
    const used = await this.prisma.projectVoice.count({ where: { voiceId: id } });
    if (used > 0) throw new ConflictException('Не удалось удалить: голос используется в проектах.');
    await this.prisma.voice.delete({ where: { id } });
  }

  /**
   * Синхронизирует голоса из файловой системы
   * Сканирует папку public/cache/voices/audio/ и создает/обновляет записи в БД
   */
  async syncFromFilesystem(basePath: string = 'public/cache/voices', force: boolean = false) {
    const fs = require('fs');
    const path = require('path');
    
    const audioDir = path.join(process.cwd(), basePath, 'audio');
    const metaFile = path.join(process.cwd(), basePath, 'meta', 'voice-metadata.json');

    if (!fs.existsSync(audioDir)) {
      throw new NotFoundException(`Audio directory not found: ${audioDir}`);
    }

    const files = fs.readdirSync(audioDir).filter((f: string) => 
      /\.(mp3|wav|ogg|m4a)$/i.test(f)
    );

    const voices: Array<{
      id: string;
      name: string;
      role: VoiceRole;
      gender: VoiceGender;
      language: string;
      style: string;
      provider: string;
      providerVoiceId: string;
    }> = [];

    const errors: string[] = [];
    let created = 0;
    let updated = 0;

    // Парсим метаданные если есть
    let metadata: Record<string, any> = {};
    if (fs.existsSync(metaFile)) {
      try {
        const metaContent = fs.readFileSync(metaFile, 'utf-8');
        const metaData = JSON.parse(metaContent);
        if (metaData.voices) {
          for (const voice of metaData.voices) {
            const fileName = voice.audioFile?.split('/').pop();
            if (fileName) {
              metadata[fileName] = voice;
            }
          }
        }
      } catch (e) {
        errors.push(`Failed to parse metadata: ${e}`);
      }
    }

    for (const fileName of files) {
      try {
        // Парсим имя файла: {role}_{index}.{ext}
        const match = fileName.match(/^(narrator|male|female)_(\d+)\.(mp3|wav|ogg|m4a)$/i);
        if (!match) {
          errors.push(`Invalid file name format: ${fileName}`);
          continue;
        }

        const [, roleStr, indexStr] = match;
        const role = roleStr.toLowerCase();
        const index = parseInt(indexStr, 10);

        // Определяем роль и пол
        let voiceRole: VoiceRole = 'actor';
        let gender: VoiceGender = 'neutral';
        
        if (role === 'narrator') {
          voiceRole = 'narrator';
          gender = 'neutral';
        } else if (role === 'male') {
          voiceRole = 'actor';
          gender = 'male';
        } else if (role === 'female') {
          voiceRole = 'actor';
          gender = 'female';
        }

        // Получаем метаданные из файла или используем дефолтные
        const meta = metadata[fileName] || {};
        const providerVoiceId = `${role}_${index}`;
        
        const voiceData = {
          name: meta.name || (role === 'narrator' ? `Диктор ${index}` : role === 'male' ? `Мужской голос ${index}` : `Женский голос ${index}`),
          role: voiceRole,
          gender: gender,
          language: meta.language || 'ru',
          style: meta.style || 'default',
          provider: 'local',
          providerVoiceId: providerVoiceId,
          characterDescription: meta.characterDescription || null,
          isActive: true,
        };

        // Проверяем существует ли голос
        const existing = await this.prisma.voice.findUnique({
          where: {
            provider_providerVoiceId: {
              provider: 'local',
              providerVoiceId: providerVoiceId,
            },
          },
        });

        if (existing) {
          if (force) {
            await this.prisma.voice.update({
              where: { id: existing.id },
              data: voiceData,
            });
            updated++;
          }
          voices.push(existing);
        } else {
          const createdVoice = await this.prisma.voice.create({
            data: voiceData,
          });
          voices.push(createdVoice);
          created++;
        }
      } catch (e: any) {
        errors.push(`Failed to process ${fileName}: ${e.message}`);
      }
    }

    return {
      success: true,
      synced: voices.length,
      created,
      updated,
      errors,
      voices: voices.map((v) => ({
        id: v.id,
        name: v.name,
        role: v.role,
        gender: v.gender,
        language: v.language,
        style: v.style,
        provider: v.provider,
        providerVoiceId: v.providerVoiceId,
      })),
    };
  }
}

