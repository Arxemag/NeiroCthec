import { BadGatewayException, Injectable, InternalServerErrorException } from '@nestjs/common';
import type { Response } from 'express';
import { Readable } from 'stream';

@Injectable()
export class TasksProxyService {
  private getCoreBase(): string {
    const base = process.env.CORE_API_URL ?? process.env.APP_API_URL ?? '';
    const norm = base.replace(/\/$/, '');
    if (!norm) {
      throw new InternalServerErrorException(
        'Core API not configured: set CORE_API_URL or APP_API_URL',
      );
    }
    return norm;
  }

  async getTaskStatus(userId: string, taskId: string): Promise<Record<string, unknown>> {
    const coreBase = this.getCoreBase();
    const url = `${coreBase}/tasks/${encodeURIComponent(taskId)}`;
    const res = await fetch(url, {
      headers: { 'X-User-Id': userId },
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new BadGatewayException(`Core getTask failed: ${res.status} ${text}`);
    }
    return res.json() as Promise<Record<string, unknown>>;
  }

  async streamTaskArtifact(userId: string, taskId: string, res: Response): Promise<void> {
    const coreBase = this.getCoreBase();
    const url = `${coreBase}/artifacts/${encodeURIComponent(taskId)}`;

    const coreRes = await fetch(url, {
      headers: { 'X-User-Id': userId },
      redirect: 'follow',
    });

    if (!coreRes.ok) {
      const text = await coreRes.text().catch(() => '');
      throw new BadGatewayException(`Core getArtifact failed: ${coreRes.status} ${text}`);
    }

    const contentType = coreRes.headers.get('content-type');
    if (contentType) res.setHeader('Content-Type', contentType);
    const contentLength = coreRes.headers.get('content-length');
    if (contentLength) res.setHeader('Content-Length', contentLength);

    // В Node fetch body — web stream. Конвертируем в node stream для pipe в express res.
    const body = coreRes.body;
    if (!body) {
      res.status(204).end();
      return;
    }

    const nodeStream = Readable.fromWeb(body as any);
    nodeStream.pipe(res);
  }
}

