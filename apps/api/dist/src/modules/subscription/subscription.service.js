"use strict";
var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
var __metadata = (this && this.__metadata) || function (k, v) {
    if (typeof Reflect === "object" && typeof Reflect.metadata === "function") return Reflect.metadata(k, v);
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.SubscriptionService = void 0;
const common_1 = require("@nestjs/common");
const prisma_service_1 = require("../prisma/prisma.service");
let SubscriptionService = class SubscriptionService {
    prisma;
    constructor(prisma) {
        this.prisma = prisma;
    }
    async getForUser(userId) {
        const user = await this.prisma.user.findUnique({
            where: { id: userId },
            include: { subscription: { include: { plan: true } } },
        });
        if (!user)
            return null;
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
    async upgradeStub(userId) {
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
};
exports.SubscriptionService = SubscriptionService;
exports.SubscriptionService = SubscriptionService = __decorate([
    (0, common_1.Injectable)(),
    __metadata("design:paramtypes", [prisma_service_1.PrismaService])
], SubscriptionService);
//# sourceMappingURL=subscription.service.js.map