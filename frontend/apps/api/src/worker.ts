import 'dotenv/config';
import { Worker } from 'bullmq';
import { PrismaClient } from '@prisma/client';
import { S3Client, PutObjectCommand, HeadBucketCommand, CreateBucketCommand } from '@aws-sdk/client-s3';

function requiredEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing env: ${name}`);
  return v;
}

function createSilenceWav(params: { seconds: number; sampleRate: number }) {
  const numChannels = 1;
  const bitsPerSample = 16;
  const blockAlign = (numChannels * bitsPerSample) / 8;
  const byteRate = params.sampleRate * blockAlign;
  const numSamples = Math.floor(params.seconds * params.sampleRate);
  const dataSize = numSamples * blockAlign;

  const buffer = Buffer.alloc(44 + dataSize);
  let o = 0;
  buffer.write('RIFF', o); o += 4;
  buffer.writeUInt32LE(36 + dataSize, o); o += 4;
  buffer.write('WAVE', o); o += 4;
  buffer.write('fmt ', o); o += 4;
  buffer.writeUInt32LE(16, o); o += 4; // PCM header size
  buffer.writeUInt16LE(1, o); o += 2; // PCM
  buffer.writeUInt16LE(numChannels, o); o += 2;
  buffer.writeUInt32LE(params.sampleRate, o); o += 4;
  buffer.writeUInt32LE(byteRate, o); o += 4;
  buffer.writeUInt16LE(blockAlign, o); o += 2;
  buffer.writeUInt16LE(bitsPerSample, o); o += 2;
  buffer.write('data', o); o += 4;
  buffer.writeUInt32LE(dataSize, o); o += 4;
  // Data already zero-filled = silence
  return buffer;
}

async function ensureBucketExists(s3: S3Client, bucket: string) {
  try {
    await s3.send(new HeadBucketCommand({ Bucket: bucket }));
  } catch {
    await s3.send(new CreateBucketCommand({ Bucket: bucket }));
  }
}

async function main() {
  const prisma = new PrismaClient();

  const s3 = new S3Client({
    region: requiredEnv('S3_REGION'),
    endpoint: requiredEnv('S3_ENDPOINT'),
    forcePathStyle: true,
    credentials: {
      accessKeyId: requiredEnv('S3_ACCESS_KEY'),
      secretAccessKey: requiredEnv('S3_SECRET_KEY'),
    },
  });
  const bucket = requiredEnv('S3_BUCKET');
  await ensureBucketExists(s3, bucket);

  const connection = process.env.REDIS_URL
    ? { url: process.env.REDIS_URL }
    : { host: '127.0.0.1', port: 6379 };

  // Worker: stub TTS generation (silence WAV)
  const worker = new Worker(
    'neurochtec',
    async (job) => {
      if (job.name !== 'generate-audio') return;
      const audioId = job.data.audioId as string;

      const audio = await prisma.audio.findUnique({ where: { id: audioId } });
      if (!audio) return;

      await prisma.audio.update({ where: { id: audioId }, data: { status: 'processing', errorMessage: null } });
      await prisma.project.update({ where: { id: audio.projectId }, data: { status: 'processing', errorMessage: null } });

      // NOTE: Replace with real TTS provider call
      const wav = createSilenceWav({ seconds: 1, sampleRate: 22050 });
      const key = `audios/${audioId}.wav`;

      await s3.send(
        new PutObjectCommand({
          Bucket: bucket,
          Key: key,
          Body: wav,
          ContentType: 'audio/wav',
        }),
      );

      await prisma.audio.update({
        where: { id: audioId },
        data: {
          status: 'ready',
          storageKey: key,
          durationSeconds: 1,
          format: 'wav',
        },
      });
      await prisma.project.update({ where: { id: audio.projectId }, data: { status: 'ready' } });
    },
    { connection },
  );

  // eslint-disable-next-line no-console
  console.log('Worker started');
  // Keep process alive
  await new Promise(() => {});

  // Unreachable, but kept for completeness
  await worker.close();
  await prisma.$disconnect();
}

main().catch((e) => {
  // eslint-disable-next-line no-console
  console.error(e);
  process.exit(1);
});

