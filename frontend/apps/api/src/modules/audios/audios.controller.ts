import { Controller, Get, Param, Post, Req, Res, UseGuards } from '@nestjs/common';
import { AccessAuthGuard } from '../auth/guards';
import { AudiosService } from './audios.service';
import { StorageService } from '../storage/storage.service';
import type { Response } from 'express';

function parseRange(rangeHeader?: string | string[]) {
  if (!rangeHeader || Array.isArray(rangeHeader)) return undefined;
  const m = /^bytes=(\d*)-(\d*)$/.exec(rangeHeader);
  if (!m) return undefined;
  const start = m[1] ? Number(m[1]) : undefined;
  const end = m[2] ? Number(m[2]) : undefined;
  return { start, end };
}

@Controller('/api')
export class AudiosController {
  constructor(
    private readonly audios: AudiosService,
    private readonly storage: StorageService,
  ) {}

  @UseGuards(AccessAuthGuard)
  @Post('/projects/:id/generate-audio')
  async generate(@Req() req: any, @Param('id') projectId: string) {
    const audio = await this.audios.enqueueGeneration(projectId, req.user.sub);
    return { audio };
  }

  @UseGuards(AccessAuthGuard)
  @Get('/projects/:id/audios')
  async list(@Req() req: any, @Param('id') projectId: string) {
    const { audios } = await this.audios.listByProject(projectId, req.user.sub);
    return {
      audios: audios.map((a) => ({
        id: a.id,
        status: a.status,
        format: a.format,
        durationSeconds: a.durationSeconds,
        createdAt: a.createdAt,
      })),
    };
  }

  @UseGuards(AccessAuthGuard)
  @Get('/audios/:id/stream')
  async stream(@Req() req: any, @Res() res: Response, @Param('id') audioId: string) {
    const audio = await this.audios.getAudioForStream(audioId, req.user.sub);
    const range = parseRange(req.headers['range']);

    const obj = await this.storage.getObjectStream({ key: audio.storageKey!, range });
    res.setHeader('Content-Type', obj.contentType);
    res.setHeader('Accept-Ranges', obj.acceptRanges ?? 'bytes');
    if (obj.contentRange) res.setHeader('Content-Range', obj.contentRange);
    if (obj.contentLength) res.setHeader('Content-Length', String(obj.contentLength));

    // If range was requested, S3 returns 206
    if (range) res.status(206);
    obj.body.pipe(res);
  }
}

