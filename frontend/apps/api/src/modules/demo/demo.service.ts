import { Injectable, NotFoundException } from '@nestjs/common';
import { randomUUID } from 'crypto';

type DemoChapter = {
  id: string;
  title: string;
  text: string;
  status: 'pending' | 'processing' | 'ready' | 'error';
  durationSeconds?: number;
  audio?: Buffer;
};

type DemoTask = {
  id: string;
  fileName: string;
  text: string;
  stage: 0 | 1 | 2 | 3 | 4 | 5;
  stageLabel: string;
  stageStartedAt: number;
  chapters: DemoChapter[];
  voiceRequested: boolean;
};

function createSilenceWav(seconds: number, sampleRate = 22050) {
  const numChannels = 1;
  const bitsPerSample = 16;
  const blockAlign = (numChannels * bitsPerSample) / 8;
  const byteRate = sampleRate * blockAlign;
  const numSamples = Math.floor(seconds * sampleRate);
  const dataSize = numSamples * blockAlign;

  const buffer = Buffer.alloc(44 + dataSize);
  let o = 0;
  buffer.write('RIFF', o); o += 4;
  buffer.writeUInt32LE(36 + dataSize, o); o += 4;
  buffer.write('WAVE', o); o += 4;
  buffer.write('fmt ', o); o += 4;
  buffer.writeUInt32LE(16, o); o += 4;
  buffer.writeUInt16LE(1, o); o += 2;
  buffer.writeUInt16LE(numChannels, o); o += 2;
  buffer.writeUInt32LE(sampleRate, o); o += 4;
  buffer.writeUInt32LE(byteRate, o); o += 4;
  buffer.writeUInt16LE(blockAlign, o); o += 2;
  buffer.writeUInt16LE(bitsPerSample, o); o += 2;
  buffer.write('data', o); o += 4;
  buffer.writeUInt32LE(dataSize, o); o += 4;
  return buffer;
}

@Injectable()
export class DemoService {
  private readonly tasks = new Map<string, DemoTask>();

  createTask(fileName: string, text: string) {
    const id = randomUUID();
    const task: DemoTask = {
      id,
      fileName,
      text,
      stage: 0,
      stageLabel: 'Книга загружена',
      stageStartedAt: Date.now(),
      chapters: [],
      voiceRequested: false,
    };

    this.tasks.set(id, task);
    this.runPreVoiceStages(task).catch(() => {
      task.stage = 5;
      task.stageLabel = 'Ошибка обработки';
    });

    return this.serializeTask(task);
  }

  getTask(taskId: string) {
    const task = this.tasks.get(taskId);
    if (!task) throw new NotFoundException('Task not found');
    return this.serializeTask(task);
  }

  async startVoice(taskId: string) {
    const task = this.tasks.get(taskId);
    if (!task) throw new NotFoundException('Task not found');
    if (task.stage < 3) return this.serializeTask(task);
    if (task.stage >= 4) return this.serializeTask(task);

    task.voiceRequested = true;
    task.stage = 4;
    task.stageLabel = 'Stage 4: отправлено в контейнер озвучки';
    task.stageStartedAt = Date.now();

    this.runVoiceStage(task).catch(() => {
      task.stage = 5;
      task.stageLabel = 'Ошибка озвучки';
      task.chapters = task.chapters.map((c) => ({ ...c, status: 'error' }));
    });

    return this.serializeTask(task);
  }

  getChapterAudio(taskId: string, chapterId: string) {
    const task = this.tasks.get(taskId);
    if (!task) throw new NotFoundException('Task not found');
    const chapter = task.chapters.find((c) => c.id === chapterId);
    if (!chapter || !chapter.audio) throw new NotFoundException('Chapter audio not found');
    return chapter.audio;
  }

  private async runPreVoiceStages(task: DemoTask) {
    await this.switchStage(task, 1, 'Stage 1: извлечение текста');
    await this.switchStage(task, 2, 'Stage 2: очистка и нормализация');
    task.chapters = this.splitChapters(task.text).map((c, i) => ({
      id: randomUUID(),
      title: `Глава ${i + 1}${c.title ? ` — ${c.title}` : ''}`,
      text: c.text,
      status: 'pending',
    }));
    await this.switchStage(task, 3, 'Stage 3: книга разбита на главы, ожидаем озвучку');
  }

  private async runVoiceStage(task: DemoTask) {
    for (const chapter of task.chapters) {
      chapter.status = 'processing';
      const durationSeconds = Math.max(2, Math.ceil(chapter.text.length / 450));
      await this.sleep(500);
      chapter.audio = createSilenceWav(durationSeconds);
      chapter.durationSeconds = durationSeconds;
      chapter.status = 'ready';
    }

    task.stage = 5;
    task.stageLabel = 'Stage 5: главы озвучены и доступны в плеере';
    task.stageStartedAt = Date.now();
  }

  private async switchStage(task: DemoTask, stage: 1 | 2 | 3, label: string) {
    task.stage = stage;
    task.stageLabel = label;
    task.stageStartedAt = Date.now();
    await this.sleep(900);
  }

  private sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  private splitChapters(text: string) {
    const normalized = text.replace(/\r\n/g, '\n').trim();
    const byHeading = normalized.split(/\n(?=Глава\s+\d+|Chapter\s+\d+)/i).filter(Boolean);

    if (byHeading.length > 1) {
      return byHeading.map((chunk) => {
        const [first, ...rest] = chunk.split('\n');
        return { title: first.trim(), text: rest.join('\n').trim() || chunk.trim() };
      });
    }

    const paragraphs = normalized.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
    const chunks: { title: string; text: string }[] = [];
    let current = '';
    for (const p of paragraphs) {
      if ((current + '\n\n' + p).length > 2500 && current) {
        chunks.push({ title: '', text: current });
        current = p;
      } else {
        current = current ? `${current}\n\n${p}` : p;
      }
    }
    if (current) chunks.push({ title: '', text: current });

    return chunks.length ? chunks : [{ title: '', text: normalized }];
  }

  private serializeTask(task: DemoTask) {
    return {
      id: task.id,
      fileName: task.fileName,
      stage: task.stage,
      stageLabel: task.stageLabel,
      stageStartedAt: task.stageStartedAt,
      voiceRequested: task.voiceRequested,
      chapters: task.chapters.map((c) => ({
        id: c.id,
        title: c.title,
        textLength: c.text.length,
        status: c.status,
        durationSeconds: c.durationSeconds ?? null,
      })),
    };
  }
}
