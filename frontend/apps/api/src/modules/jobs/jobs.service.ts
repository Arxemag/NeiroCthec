import { Injectable } from '@nestjs/common';
import { Queue } from 'bullmq';

export type GenerateAudioJob = {
  audioId: string;
};

@Injectable()
export class JobsService {
  private queue: Queue;

  constructor() {
    const connection = process.env.REDIS_URL
      ? { url: process.env.REDIS_URL }
      : { host: '127.0.0.1', port: 6379 };

    this.queue = new Queue('neurochtec', { connection });
  }

  async enqueueGenerateAudio(job: GenerateAudioJob) {
    await this.queue.add('generate-audio', job, {
      removeOnComplete: 1000,
      removeOnFail: 1000,
    });
  }
}

