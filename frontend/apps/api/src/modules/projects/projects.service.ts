import {
  BadGatewayException,
  BadRequestException,
  ForbiddenException,
  HttpException,
  HttpStatus,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import type { Prisma } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class ProjectsService {
  constructor(private readonly prisma: PrismaService) {}

  async listByUser(userId: string) {
    return this.prisma.project.findMany({
      where: { userId, deletedAt: null },
      orderBy: { updatedAt: 'desc' },
      include: { audios: { orderBy: { createdAt: 'desc' }, take: 1 } },
    });
  }

  async getByIdForUser(projectId: string, userId: string) {
    const project = await this.prisma.project.findUnique({
      where: { id: projectId },
      include: {
        voices: { include: { voice: true } },
        voiceSettings: true,
      },
    });
    if (!project) throw new NotFoundException('Project not found');
    if (project.userId !== userId) throw new ForbiddenException();
    if (project.deletedAt) throw new NotFoundException('Project not found');
    return project;
  }

  async create(userId: string, data: { title: string; text: string; language: string; voiceIds: string[] }) {
    if (data.voiceIds.length === 0) throw new BadRequestException('At least one voice required');
    const validVoices = await this.prisma.voice.findMany({
      where: { id: { in: data.voiceIds }, isActive: true },
      select: { id: true },
    });
    const validIds = validVoices.map((v) => v.id);
    const coreConfigured = !!(process.env.APP_API_URL || process.env.CORE_API_URL);
    const useCoreVoices = validIds.length === 0 && coreConfigured && data.voiceIds.length > 0;

    if (validIds.length === 0 && !useCoreVoices) {
      throw new BadRequestException(
        'Указанные голоса не найдены в базе. При использовании App API (Core) голоса хранятся отдельно.',
      );
    }

    if (useCoreVoices) {
      return this.prisma.project.create({
        data: {
          userId,
          title: data.title,
          text: data.text,
          language: data.language,
          voiceSettings: {
            create: {
              narratorVoiceId: data.voiceIds[0],
              maleVoiceId: data.voiceIds[1] ?? undefined,
              femaleVoiceId: data.voiceIds[2] ?? undefined,
            },
          },
        },
        include: { voices: true, voiceSettings: true },
      });
    }

    return this.prisma.project.create({
      data: {
        userId,
        title: data.title,
        text: data.text,
        language: data.language,
        voices: {
          create: validIds.map((voiceId) => ({ voiceId })),
        },
      },
      include: { voices: true, voiceSettings: true },
    });
  }

  async update(
    projectId: string,
    userId: string,
    patch: {
      title?: string;
      text?: string;
      language?: string;
      voiceIds?: string[];
      speakerSettings?: { narrator?: { tempo?: number; pitch?: number }; male?: { tempo?: number; pitch?: number }; female?: { tempo?: number; pitch?: number } };
      voiceSettings?: { narratorVoiceId?: string | null; maleVoiceId?: string | null; femaleVoiceId?: string | null };
    },
  ) {
    const existing = await this.prisma.project.findUnique({ where: { id: projectId } });
    if (!existing) throw new NotFoundException('Project not found');
    if (existing.userId !== userId) throw new ForbiddenException();
    if (existing.deletedAt) throw new NotFoundException('Project not found');

    const coreConfigured = !!(process.env.APP_API_URL || process.env.CORE_API_URL);

    return this.prisma.$transaction(async (tx: Prisma.TransactionClient) => {
      if (patch.voiceIds && patch.voiceIds.length > 0) {
        const existingVoices = await tx.voice.findMany({
          where: { id: { in: patch.voiceIds }, isActive: true },
          select: { id: true },
        });
        const validIds = existingVoices.map((v) => v.id);
        await tx.projectVoice.deleteMany({ where: { projectId } });
        if (validIds.length > 0) {
          await tx.projectVoice.createMany({
            data: validIds.map((voiceId) => ({ projectId, voiceId })),
            skipDuplicates: true,
          });
        } else if (coreConfigured) {
          await tx.projectVoiceSettings.upsert({
            where: { projectId },
            create: {
              projectId,
              narratorVoiceId: patch.voiceIds[0],
              maleVoiceId: patch.voiceIds[1] ?? undefined,
              femaleVoiceId: patch.voiceIds[2] ?? undefined,
            },
            update: {
              narratorVoiceId: patch.voiceIds[0],
              maleVoiceId: patch.voiceIds[1] ?? undefined,
              femaleVoiceId: patch.voiceIds[2] ?? undefined,
            },
          });
        }
      }

      const data: Prisma.ProjectUpdateInput = {
        title: patch.title,
        text: patch.text,
        language: patch.language,
      };
      if (patch.speakerSettings !== undefined) {
        data.speakerSettings = patch.speakerSettings as object;
      }

      const updated = await tx.project.update({
        where: { id: projectId },
        data,
        include: { voices: { include: { voice: true } }, voiceSettings: true },
      });

      if (patch.voiceSettings !== undefined) {
        const vs = patch.voiceSettings;
        await tx.projectVoiceSettings.upsert({
          where: { projectId },
          create: {
            projectId,
            narratorVoiceId: vs.narratorVoiceId ?? undefined,
            maleVoiceId: vs.maleVoiceId ?? undefined,
            femaleVoiceId: vs.femaleVoiceId ?? undefined,
          },
          update: {
            narratorVoiceId: vs.narratorVoiceId ?? undefined,
            maleVoiceId: vs.maleVoiceId ?? undefined,
            femaleVoiceId: vs.femaleVoiceId ?? undefined,
          },
        });
        const withSettings = await tx.project.findUnique({
          where: { id: projectId },
          include: { voices: { include: { voice: true } }, voiceSettings: true },
        });
        return withSettings!;
      }

      return updated;
    });
  }

  async delete(projectId: string, userId: string) {
    const existing = await this.prisma.project.findUnique({ where: { id: projectId } });
    if (!existing) throw new NotFoundException('Project not found');
    if (existing.userId !== userId) throw new ForbiddenException();
    if (existing.deletedAt) return; // уже в корзине
    await this.prisma.project.update({
      where: { id: projectId },
      data: { deletedAt: new Date() },
    });
  }

  private static TRASH_TTL_MS = 72 * 60 * 60 * 1000; // 72 часа

  async listTrashByUser(userId: string) {
    const cutoff = new Date(Date.now() - ProjectsService.TRASH_TTL_MS);
    await this.prisma.project.deleteMany({
      where: { userId, deletedAt: { not: null, lt: cutoff } },
    });
    return this.prisma.project.findMany({
      where: { userId, deletedAt: { not: null, gte: cutoff } },
      orderBy: { deletedAt: 'desc' },
      select: { id: true, title: true, language: true, status: true, deletedAt: true },
    });
  }

  async restore(projectId: string, userId: string) {
    const existing = await this.prisma.project.findUnique({ where: { id: projectId } });
    if (!existing) throw new NotFoundException('Project not found');
    if (existing.userId !== userId) throw new ForbiddenException();
    if (!existing.deletedAt) return this.getByIdForUser(projectId, userId);
    return this.prisma.project.update({
      where: { id: projectId },
      data: { deletedAt: null },
      include: { voices: { include: { voice: true } } },
    });
  }

  /** Пометить проект как завершённый (status = ready). */
  async complete(projectId: string, userId: string) {
    const existing = await this.prisma.project.findUnique({ where: { id: projectId } });
    if (!existing) throw new NotFoundException('Project not found');
    if (existing.userId !== userId) throw new ForbiddenException();
    if (existing.deletedAt) throw new NotFoundException('Project not found');
    return this.prisma.project.update({
      where: { id: projectId },
      data: { status: 'ready', errorMessage: null },
      include: { voices: { include: { voice: true } } },
    });
  }

  /** Список «глав» проекта: по одному элементу на каждый Audio, порядок по createdAt. */
  async getChapters(projectId: string, userId: string) {
    const project = await this.prisma.project.findUnique({
      where: { id: projectId },
      include: {
        audios: { orderBy: { createdAt: 'asc' } },
      },
    });
    if (!project) throw new NotFoundException('Project not found');
    if (project.userId !== userId) throw new ForbiddenException();
    if (project.deletedAt) throw new NotFoundException('Project not found');
    const chapters = project.audios.map((a, i) => ({
      id: a.id,
      title: `Глава ${i + 1}`,
      audioId: a.id,
      durationSeconds: a.durationSeconds ?? undefined,
      createdAt: a.createdAt,
    }));
    return { chapters };
  }

  /** Обновить текст проекта (для upload-text). Проверка прав внутри. */
  async setText(projectId: string, userId: string, text: string) {
    const existing = await this.prisma.project.findUnique({ where: { id: projectId } });
    if (!existing) throw new NotFoundException('Project not found');
    if (existing.userId !== userId) throw new ForbiddenException();
    if (existing.deletedAt) throw new NotFoundException('Project not found');
    await this.prisma.project.update({
      where: { id: projectId },
      data: { text },
    });
    return { ok: true };
  }

  /**
   * Превью по спикерам (narrator, male, female): прокси к Core, если настроен CORE_API_URL / APP_API_URL.
   * Иначе вызывающий код должен обработать 501 (превью может отдаваться напрямую с Core).
   */
  async previewBySpeakers(
    projectId: string,
    userId: string,
    body?: { bookId?: string },
  ): Promise<{ narrator?: string; male?: string; female?: string } | { urls: { narrator?: string; male?: string; female?: string } }> {
    await this.getByIdForUser(projectId, userId);

    const base = process.env.CORE_API_URL ?? process.env.APP_API_URL ?? '';
    if (!base) {
      throw new HttpException(
        'Preview by speakers not configured: set CORE_API_URL or APP_API_URL to proxy to Core',
        HttpStatus.NOT_IMPLEMENTED,
      );
    }

    const url = `${base.replace(/\/$/, '')}/internal/preview-by-speakers`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectId, bookId: body?.bookId ?? projectId }),
    });

    if (!res.ok) {
      const text = await res.text();
      throw new BadGatewayException(`Core preview failed: ${res.status} ${text}`);
    }

    return (await res.json()) as { narrator?: string; male?: string; female?: string } | { urls: { narrator?: string; male?: string; female?: string } };
  }
}

