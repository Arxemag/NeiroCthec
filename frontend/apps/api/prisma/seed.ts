import 'dotenv/config';
import { PrismaClient, SubscriptionStatus, UserRole, VoiceGender } from '@prisma/client';
import * as argon2 from 'argon2';

const prisma = new PrismaClient();

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
      gender: VoiceGender.female,
      language: 'ru-RU',
      style: 'neutral',
      provider: 'stub',
      providerVoiceId: 'ru-anna-neutral',
    },
    {
      name: 'Максим',
      gender: VoiceGender.male,
      language: 'ru-RU',
      style: 'narration',
      provider: 'stub',
      providerVoiceId: 'ru-maxim-narration',
    },
    {
      name: 'Alex',
      gender: VoiceGender.neutral,
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
      role: UserRole.admin,
      subscriptionStatus: SubscriptionStatus.active,
      subscription: {
        create: {
          status: SubscriptionStatus.active,
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

