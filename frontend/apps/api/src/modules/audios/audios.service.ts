import { BadRequestException, ForbiddenException, Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { JobsService } from '../jobs/jobs.service';

function envInt(name: string, fallback: number): number {
  const v = Number(process.env[name]);
  return Number.isFinite(v) ? v : fallback;
}

@Injectable()
export class AudiosService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly jobs: JobsService,
  ) {}

  async listByProject(projectId: string, userId: string) {
    const project = await this.prisma.project.findUnique({ where: { id: projectId } });
    if (!project) throw new NotFoundException('Project not found');
    if (project.userId !== userId) throw new ForbiddenException();

    const audios = await this.prisma.audio.findMany({
      where: { projectId },
      orderBy: { createdAt: 'desc' },
    });

    return { project, audios };
  }

  async enqueueGeneration(projectId: string, userId: string) {
    const project = await this.prisma.project.findUnique({ where: { id: projectId } });
    if (!project) throw new NotFoundException('Project not found');
    if (project.userId !== userId) throw new ForbiddenException();

    const user = await this.prisma.user.findUnique({ where: { id: userId } });
    if (!user) throw new ForbiddenException();

    const maxChars = envInt('FREE_MAX_CHARS_PER_REQUEST', 6000);
    if (user.subscriptionStatus !== 'active' && project.text.length > maxChars) {
      throw new BadRequestException(`Text is too long for free plan (max ${maxChars} chars per request)`);
    }

    const maxPerDay = envInt('FREE_MAX_REQUESTS_PER_DAY', 5);
    if (user.subscriptionStatus !== 'active') {
      const since = new Date();
      since.setHours(0, 0, 0, 0);
      const countToday = await this.prisma.audio.count({
        where: { userId, createdAt: { gte: since } },
      });
      if (countToday >= maxPerDay) throw new BadRequestException('Daily free limit reached');
    }

    const audio = await this.prisma.audio.create({
      data: {
        projectId,
        userId,
        status: 'queued',
      },
    });

    await this.prisma.project.update({
      where: { id: projectId },
      data: { status: 'queued', errorMessage: null },
    });

    await this.jobs.enqueueGenerateAudio({ audioId: audio.id });
    return audio;
  }

  async getAudioForStream(audioId: string, userId: string) {
    const audio = await this.prisma.audio.findUnique({ where: { id: audioId } });
    if (!audio) throw new NotFoundException('Audio not found');
    if (audio.userId !== userId) throw new ForbiddenException();
    if (audio.status !== 'ready' || !audio.storageKey) throw new BadRequestException('Audio not ready');
    return audio;
  }
}

