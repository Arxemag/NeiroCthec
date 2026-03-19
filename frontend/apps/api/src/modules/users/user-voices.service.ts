import { ForbiddenException, Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import type { CreateUserVoiceDto, UpdateUserVoiceDto } from './user-voices.dto';

@Injectable()
export class UserVoicesService {
  constructor(private readonly prisma: PrismaService) {}

  async listByUser(userId: string, projectId?: string | null) {
    const where: { userId: string; projectId?: string | null } = { userId };
    if (projectId !== undefined) where.projectId = projectId;
    return this.prisma.userVoice.findMany({
      where,
      orderBy: { createdAt: 'desc' },
    });
  }

  /** Список голосов пользователя + привязанных к проекту (для GET /api/projects/:id/voices) */
  async listForProject(userId: string, projectId: string) {
    const items = await this.prisma.userVoice.findMany({
      where: {
        userId,
        OR: [{ projectId: null }, { projectId }],
      },
      orderBy: { createdAt: 'desc' },
    });
    return items;
  }

  async create(userId: string, dto: CreateUserVoiceDto) {
    return this.prisma.userVoice.create({
      data: {
        userId,
        name: dto.name,
        coreVoiceId: dto.coreVoiceId,
        projectId: dto.projectId ?? undefined,
      },
    });
  }

  async update(id: string, userId: string, dto: UpdateUserVoiceDto) {
    const existing = await this.prisma.userVoice.findUnique({ where: { id } });
    if (!existing) throw new NotFoundException('User voice not found');
    if (existing.userId !== userId) throw new ForbiddenException();
    const data: { name?: string; projectId?: string | null } = {};
    if (dto.name !== undefined) data.name = dto.name;
    if (dto.projectId !== undefined) data.projectId = dto.projectId;
    if (Object.keys(data).length === 0) return existing;
    return this.prisma.userVoice.update({
      where: { id },
      data,
    });
  }

  async delete(id: string, userId: string) {
    const existing = await this.prisma.userVoice.findUnique({ where: { id } });
    if (!existing) throw new NotFoundException('User voice not found');
    if (existing.userId !== userId) throw new ForbiddenException();
    await this.prisma.userVoice.delete({ where: { id } });
  }

  async getByIdForUser(id: string, userId: string) {
    const v = await this.prisma.userVoice.findUnique({ where: { id } });
    if (!v || v.userId !== userId) throw new NotFoundException('User voice not found');
    return v;
  }
}
