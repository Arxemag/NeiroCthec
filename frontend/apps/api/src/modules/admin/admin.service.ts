import { Injectable, NotFoundException } from '@nestjs/common';
import type { AudioStatus, ProjectStatus, SubscriptionStatus } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import { AuthService } from '../auth/auth.service';

@Injectable()
export class AdminService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly auth: AuthService,
  ) {}

  async listUsers() {
    return this.prisma.user.findMany({
      orderBy: { createdAt: 'desc' },
      select: {
        id: true,
        email: true,
        role: true,
        subscriptionStatus: true,
        createdAt: true,
        _count: {
          select: {
            projects: true,
            audios: true,
          },
        },
        subscription: {
          select: {
            status: true,
            plan: { select: { name: true } },
          },
        },
      },
    });
  }

  async getUserDetail(id: string) {
    const user = await this.prisma.user.findUnique({
      where: { id },
      select: {
        id: true,
        email: true,
        role: true,
        subscriptionStatus: true,
        createdAt: true,
        updatedAt: true,
        projects: {
          where: { deletedAt: null },
          orderBy: { updatedAt: 'desc' },
          select: {
            id: true,
            title: true,
            status: true,
            language: true,
            createdAt: true,
            _count: { select: { audios: true } },
          },
        },
        _count: { select: { audios: true } },
        subscription: {
          select: {
            status: true,
            plan: { select: { name: true } },
          },
        },
      },
    });
    if (!user) throw new NotFoundException('User not found');
    return user;
  }

  async changeUserPassword(userId: string, newPassword: string) {
    await this.auth.setUserPassword(userId, newPassword);
    return { ok: true };
  }

  async getMetrics() {
    const [
      totalUsers,
      totalProjects,
      totalAudios,
      projectsByStatus,
      audiosByStatus,
      subscriptionByStatus,
      newUsers7d,
      newUsers30d,
      projects7d,
      audios7d,
    ] = await Promise.all([
      this.prisma.user.count(),
      this.prisma.project.count({ where: { deletedAt: null } }),
      this.prisma.audio.count(),
      this.prisma.project.groupBy({
        by: ['status'],
        where: { deletedAt: null },
        _count: { id: true },
      }),
      this.prisma.audio.groupBy({
        by: ['status'],
        _count: { id: true },
      }),
      this.prisma.user.groupBy({
        by: ['subscriptionStatus'],
        _count: { id: true },
      }),
      this.prisma.user.count({
        where: { createdAt: { gte: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000) } },
      }),
      this.prisma.user.count({
        where: { createdAt: { gte: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000) } },
      }),
      this.prisma.project.count({
        where: { createdAt: { gte: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000) }, deletedAt: null },
      }),
      this.prisma.audio.count({
        where: { createdAt: { gte: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000) } },
      }),
    ]);

    return {
      totalUsers,
      totalProjects,
      totalAudios,
      projectsByStatus: Object.fromEntries(projectsByStatus.map((p: { status: ProjectStatus; _count: { id: number } }) => [p.status, p._count.id])),
      audiosByStatus: Object.fromEntries(audiosByStatus.map((a: { status: AudioStatus; _count: { id: number } }) => [a.status, a._count.id])),
      subscriptionByStatus: Object.fromEntries(subscriptionByStatus.map((s: { subscriptionStatus: SubscriptionStatus; _count: { id: number } }) => [s.subscriptionStatus, s._count.id])),
      newUsersLast7Days: newUsers7d,
      newUsersLast30Days: newUsers30d,
      projectsCreatedLast7Days: projects7d,
      audiosCreatedLast7Days: audios7d,
    };
  }
}
