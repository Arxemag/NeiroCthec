import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class SubscriptionService {
  constructor(private readonly prisma: PrismaService) {}

  async getForUser(userId: string) {
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
      include: { subscription: { include: { plan: true } } },
    });
    if (!user) return null;

    return {
      status: user.subscriptionStatus,
      plan: user.subscription?.plan
        ? {
            id: user.subscription.plan.id,
            name: user.subscription.plan.name,
            monthlyPriceCents: user.subscription.plan.monthlyPriceCents,
            maxCharactersMonth: user.subscription.plan.maxCharactersMonth,
            canDownload: user.subscription.plan.canDownload,
          }
        : null,
    };
  }

  // MVP stub: flips status to active and binds Pro plan if exists
  async upgradeStub(userId: string) {
    const pro = await this.prisma.plan.findFirst({ where: { name: 'Pro' } });
    const now = new Date();
    const monthLater = new Date(Date.now() + 30 * 24 * 3600 * 1000);

    await this.prisma.user.update({
      where: { id: userId },
      data: { subscriptionStatus: 'active' },
    });

    await this.prisma.subscription.upsert({
      where: { userId },
      create: {
        userId,
        status: 'active',
        planId: pro?.id ?? null,
        currentPeriodStart: now,
        currentPeriodEnd: monthLater,
      },
      update: {
        status: 'active',
        planId: pro?.id ?? null,
        currentPeriodStart: now,
        currentPeriodEnd: monthLater,
      },
    });

    return this.getForUser(userId);
  }
}

