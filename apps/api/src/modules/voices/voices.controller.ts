import { Controller, Get, Param, Query, Res, UseGuards } from '@nestjs/common';
import { VoicesService } from './voices.service';
import { AccessAuthGuard } from '../auth/guards';
import { StorageService } from '../storage/storage.service';
import type { Response } from 'express';

@Controller('/api/voices')
export class VoicesController {
  constructor(
    private readonly voices: VoicesService,
    private readonly storage: StorageService,
  ) {}

  @UseGuards(AccessAuthGuard)
  @Get()
  async list(@Query('language') language?: string, @Query('gender') gender?: string, @Query('style') style?: string) {
    const items = await this.voices.list({ language, gender, style });
    return {
      voices: items.map((v) => ({
        id: v.id,
        name: v.name,
        gender: v.gender,
        language: v.language,
        style: v.style,
        provider: v.provider,
        isActive: v.isActive,
        hasSample: Boolean(v.sampleStorageKey),
      })),
    };
  }

  @UseGuards(AccessAuthGuard)
  @Get('/:id')
  async get(@Param('id') id: string) {
    const v = await this.voices.getById(id);
    return {
      voice: {
        id: v.id,
        name: v.name,
        gender: v.gender,
        language: v.language,
        style: v.style,
        provider: v.provider,
        isActive: v.isActive,
        hasSample: Boolean(v.sampleStorageKey),
      },
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
}

