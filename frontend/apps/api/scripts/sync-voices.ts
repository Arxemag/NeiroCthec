/**
 * Скрипт для синхронизации голосов из файловой системы в базу данных
 * 
 * Запуск: npx ts-node -T scripts/sync-voices.ts
 */

import { PrismaClient, VoiceRole, VoiceGender } from '@prisma/client';
import * as fs from 'fs';
import * as path from 'path';

const prisma = new PrismaClient();

async function syncVoices() {
  const basePath = path.join(process.cwd(), '..', 'web', 'public', 'cache', 'voices');
  const audioDir = path.join(basePath, 'audio');
  const metaFile = path.join(basePath, 'meta', 'voice-metadata.json');

  console.log('📁 Scanning audio directory:', audioDir);

  if (!fs.existsSync(audioDir)) {
    console.error('❌ Audio directory not found:', audioDir);
    process.exit(1);
  }

  const files = fs.readdirSync(audioDir).filter((f) => /\.(mp3|wav|ogg|m4a)$/i.test(f));
  console.log(`📄 Found ${files.length} audio files`);

  // Парсим метаданные если есть
  const metadata: Record<string, any> = {};
  if (fs.existsSync(metaFile)) {
    try {
      const metaContent = fs.readFileSync(metaFile, 'utf-8');
      const metaData = JSON.parse(metaContent);
      if (metaData.voices) {
        for (const voice of metaData.voices) {
          const fileName = voice.audioFile?.split('/').pop();
          if (fileName) {
            metadata[fileName] = voice;
          }
        }
        console.log(`📋 Loaded metadata for ${Object.keys(metadata).length} voices`);
      }
    } catch (e) {
      console.warn('⚠️  Failed to parse metadata:', e);
    }
  }

  let created = 0;
  let updated = 0;
  const errors: string[] = [];

  for (const fileName of files) {
    try {
      // Парсим имя файла: {role}_{index}.{ext}
      const match = fileName.match(/^(narrator|male|female)_(\d+)\.(mp3|wav|ogg|m4a)$/i);
      if (!match) {
        errors.push(`Invalid file name format: ${fileName}`);
        continue;
      }

      const [, roleStr, indexStr] = match;
      const role = roleStr.toLowerCase();
      const index = parseInt(indexStr, 10);

      // Определяем роль и пол
      let voiceRole: VoiceRole = 'actor';
      let gender: VoiceGender = 'neutral';

      if (role === 'narrator') {
        voiceRole = 'narrator';
        gender = 'neutral';
      } else if (role === 'male') {
        voiceRole = 'actor';
        gender = 'male';
      } else if (role === 'female') {
        voiceRole = 'actor';
        gender = 'female';
      }

      // Получаем метаданные из файла или используем дефолтные
      const meta = metadata[fileName] || {};
      const providerVoiceId = `${role}_${index}`;

      const voiceData = {
        name:
          meta.name ||
          (role === 'narrator'
            ? `Диктор ${index}`
            : role === 'male'
              ? `Мужской голос ${index}`
              : `Женский голос ${index}`),
        role: voiceRole,
        gender: gender,
        language: meta.language || 'ru',
        style: meta.style || 'default',
        provider: 'local',
        providerVoiceId: providerVoiceId,
        characterDescription: meta.characterDescription || null,
        isActive: true,
      };

      // Проверяем существует ли голос
      const existing = await prisma.voice.findUnique({
        where: {
          provider_providerVoiceId: {
            provider: 'local',
            providerVoiceId: providerVoiceId,
          },
        },
      });

      if (existing) {
        await prisma.voice.update({
          where: { id: existing.id },
          data: voiceData,
        });
        updated++;
        console.log(`✅ Updated: ${voiceData.name}`);
      } else {
        const createdVoice = await prisma.voice.create({
          data: voiceData,
        });
        created++;
        console.log(`✨ Created: ${voiceData.name}`);
      }
    } catch (e: any) {
      const errorMsg = `Failed to process ${fileName}: ${e.message}`;
      errors.push(errorMsg);
      console.error(`❌ ${errorMsg}`);
    }
  }

  console.log('\n📊 Summary:');
  console.log(`   Created: ${created}`);
  console.log(`   Updated: ${updated}`);
  console.log(`   Total: ${created + updated}`);
  if (errors.length > 0) {
    console.log(`   Errors: ${errors.length}`);
    errors.forEach((e) => console.error(`   - ${e}`));
  }
}

syncVoices()
  .catch((e) => {
    console.error('Fatal error:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
