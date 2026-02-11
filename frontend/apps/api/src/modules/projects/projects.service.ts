import { BadRequestException, ForbiddenException, Injectable, NotFoundException } from '@nestjs/common';
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
      include: { voices: { include: { voice: true } } },
    });
    if (!project) throw new NotFoundException('Project not found');
    if (project.userId !== userId) throw new ForbiddenException();
    if (project.deletedAt) throw new NotFoundException('Project not found');
    return project;
  }

  async create(userId: string, data: { title: string; text: string; language: string; voiceIds: string[] }) {
    if (data.voiceIds.length === 0) throw new BadRequestException('At least one voice required');
    return this.prisma.project.create({
      data: {
        userId,
        title: data.title,
        text: data.text,
        language: data.language,
        voices: {
          create: data.voiceIds.map((voiceId) => ({ voiceId })),
        },
      },
      include: { voices: true },
    });
  }

  async update(projectId: string, userId: string, patch: { title?: string; text?: string; language?: string; voiceIds?: string[] }) {
    const existing = await this.prisma.project.findUnique({ where: { id: projectId } });
    if (!existing) throw new NotFoundException('Project not found');
    if (existing.userId !== userId) throw new ForbiddenException();
    if (existing.deletedAt) throw new NotFoundException('Project not found');

    return this.prisma.$transaction(async (tx) => {
      if (patch.voiceIds) {
        await tx.projectVoice.deleteMany({ where: { projectId } });
        await tx.projectVoice.createMany({
          data: patch.voiceIds.map((voiceId) => ({ projectId, voiceId })),
          skipDuplicates: true,
        });
      }

      return tx.project.update({
        where: { id: projectId },
        data: {
          title: patch.title,
          text: patch.text,
          language: patch.language,
        },
        include: { voices: { include: { voice: true } } },
      });
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
}

