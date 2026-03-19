import { Body, Controller, Delete, Get, Param, Patch, Post, Query, Req, Res, UseGuards } from '@nestjs/common';
import type { Voice } from '@prisma/client';
import { VoicesService } from './voices.service';
import { AccessAuthGuard } from '../auth/guards';
import { StorageService } from '../storage/storage.service';
import { UpdateVoiceDto } from './dto';
import type { Response } from 'express';
import type { Request } from 'express';

@Controller('/api/voices')
export class VoicesController {
  constructor(
    private readonly voices: VoicesService,
    private readonly storage: StorageService,
  ) {}

  @UseGuards(AccessAuthGuard)
  @Get()
  async list(
    @Req() req: Request & { user?: { sub?: string } },
    @Query('language') language?: string,
    @Query('gender') gender?: string,
    @Query('style') style?: string,
    @Query('role') role?: string,
  ) {
    const coreBase = process.env.CORE_API_URL ?? process.env.APP_API_URL ?? '';
    const userId = req.user?.sub;
    if (coreBase && userId) {
      try {
        const coreList = await this.voices.listFromCore(userId);
        if (coreList.length > 0) {
          return {
            voices: coreList.map((v) => ({
              id: v.id,
              name: v.name,
              role: v.role === 'narrator' ? 'narrator' : 'actor',
              gender: v.role === 'male' ? 'male' : v.role === 'female' ? 'female' : 'neutral',
              language: 'ru',
              style: '',
              provider: 'core',
              isActive: true,
              hasSample: true,
              characterDescription: null,
            })),
          };
        }
      } catch {
        // fallback to DB
      }
    }
    const items = await this.voices.list({ language, gender, style, role });
    return {
      voices: items.map((v: Voice) => ({
        id: v.id,
        name: v.name,
        role: v.role,
        gender: v.gender,
        language: v.language,
        style: v.style,
        provider: v.provider,
        isActive: v.isActive,
        hasSample: Boolean(v.sampleStorageKey),
        characterDescription: v.characterDescription ?? null,
      })),
    };
  }

  @UseGuards(AccessAuthGuard)
  @Get('/:id/sample')
  async sample(@Param('id') id: string, @Res() res: Response) {
    const v = await this.voices.getById(id);
    if (!v.sampleStorageKey) {
      res.status(404).json({ message: 'Sample not available' });
      return;
    }

    const obj = await this.storage.getObjectStream({ key: v.sampleStorageKey });
    res.setHeader('Content-Type', obj.contentType);
    if (obj.contentLength) res.setHeader('Content-Length', String(obj.contentLength));
    obj.body.pipe(res);
  }

  @UseGuards(AccessAuthGuard)
  @Get('/:id')
  async get(@Param('id') id: string) {
    const v = await this.voices.getById(id);
    return {
      voice: {
        id: v.id,
        name: v.name,
        role: v.role,
        gender: v.gender,
        language: v.language,
        style: v.style,
        provider: v.provider,
        isActive: v.isActive,
        hasSample: Boolean(v.sampleStorageKey),
        characterDescription: v.characterDescription ?? null,
      },
    };
  }

  @UseGuards(AccessAuthGuard)
  @Patch('/:id')
  async update(@Param('id') id: string, @Body() dto: UpdateVoiceDto) {
    const v = await this.voices.update(id, dto);
    return {
      voice: {
        id: v.id,
        name: v.name,
        role: v.role,
        gender: v.gender,
        language: v.language,
        style: v.style,
        provider: v.provider,
        isActive: v.isActive,
        hasSample: Boolean(v.sampleStorageKey),
        characterDescription: v.characterDescription ?? null,
      },
    };
  }

  @UseGuards(AccessAuthGuard)
  @Delete('/:id')
  async delete(@Param('id') id: string) {
    await this.voices.delete(id);
    return { ok: true };
  }

  @UseGuards(AccessAuthGuard)
  @Post('/sync-from-filesystem')
  async syncFromFilesystem(
    @Body() body: { basePath?: string; force?: boolean } = {},
  ) {
    const result = await this.voices.syncFromFilesystem(
      body.basePath || 'public/cache/voices',
      body.force || false,
    );
    return result;
  }
}

