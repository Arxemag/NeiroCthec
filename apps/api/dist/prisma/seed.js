"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
require("dotenv/config");
const client_1 = require("@prisma/client");
const argon2 = __importStar(require("argon2"));
const prisma = new client_1.PrismaClient();
async function main() {
    // Plans (stub)
    const freePlan = await prisma.plan.upsert({
        where: { name: 'Free' },
        create: {
            name: 'Free',
            monthlyPriceCents: 0,
            maxCharactersMonth: 20000,
            canDownload: false,
        },
        update: {},
    });
    await prisma.plan.upsert({
        where: { name: 'Pro' },
        create: {
            name: 'Pro',
            monthlyPriceCents: 1490 * 100,
            maxCharactersMonth: 300000,
            canDownload: true,
        },
        update: {},
    });
    // Voices
    const voices = [
        {
            name: 'Анна',
            gender: client_1.VoiceGender.female,
            language: 'ru-RU',
            style: 'neutral',
            provider: 'stub',
            providerVoiceId: 'ru-anna-neutral',
        },
        {
            name: 'Максим',
            gender: client_1.VoiceGender.male,
            language: 'ru-RU',
            style: 'narration',
            provider: 'stub',
            providerVoiceId: 'ru-maxim-narration',
        },
        {
            name: 'Alex',
            gender: client_1.VoiceGender.neutral,
            language: 'en-US',
            style: 'ad',
            provider: 'stub',
            providerVoiceId: 'en-alex-ad',
        },
    ];
    for (const v of voices) {
        await prisma.voice.upsert({
            where: { provider_providerVoiceId: { provider: v.provider, providerVoiceId: v.providerVoiceId } },
            create: v,
            update: { ...v },
        });
    }
    // Admin user (optional)
    const adminEmail = 'admin@neurochtec.local';
    const adminPassword = 'admin12345';
    const passwordHash = await argon2.hash(adminPassword);
    const admin = await prisma.user.upsert({
        where: { email: adminEmail },
        create: {
            email: adminEmail,
            passwordHash,
            role: client_1.UserRole.admin,
            subscriptionStatus: client_1.SubscriptionStatus.active,
            subscription: {
                create: {
                    status: client_1.SubscriptionStatus.active,
                    planId: freePlan.id,
                    currentPeriodStart: new Date(),
                    currentPeriodEnd: new Date(Date.now() + 30 * 24 * 3600 * 1000),
                },
            },
        },
        update: {},
        include: { subscription: true },
    });
    console.log('Seeded admin:', { email: admin.email, password: adminPassword });
}
main()
    .catch((e) => {
    console.error(e);
    process.exit(1);
})
    .finally(async () => {
    await prisma.$disconnect();
});
//# sourceMappingURL=seed.js.map