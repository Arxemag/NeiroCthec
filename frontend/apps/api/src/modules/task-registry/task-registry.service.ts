import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import type { RenderTask } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import type { CreateRenderTaskDto, CompleteRenderTaskDto } from './dto';
import type { UpsertRenderAssemblyDto } from './assembly.dto';

export type TaskRegistryInternalResult = { task: RenderTask };

export type TaskRegistryAssemblyResult = { assembly: any };

@Injectable()
export class TaskRegistryService {
  constructor(private readonly prisma: PrismaService) {}

  async getTask(taskId: string): Promise<TaskRegistryInternalResult> {
    const task = await this.prisma.renderTask.findUnique({ where: { taskId } });
    if (!task) throw new NotFoundException('RenderTask not found');
    return { task };
  }

  async upsertTask(payload: CreateRenderTaskDto): Promise<TaskRegistryInternalResult> {
    const {
      taskId,
      clientId,
      bookId,
      lineId,
      chapterId,
      speaker,
      lineType,
      emotion,
      isChapterHeader,
      isSegment,
      segmentIndex,
      segmentTotal,
      baseLineId,
      engine,
    } = payload;
    if (!clientId.trim() || !bookId.trim()) throw new BadRequestException('clientId/bookId required');

    const task = await this.prisma.renderTask.upsert({
      where: { taskId },
      update: {
        clientId,
        bookId,
        lineId,
        chapterId: chapterId ?? null,
        speaker: speaker ?? null,
        lineType: lineType ?? null,
        emotion: (emotion ?? undefined) as any,
        isChapterHeader: isChapterHeader != null ? Boolean(isChapterHeader) : null,
        isSegment: isSegment != null ? Boolean(isSegment) : null,
        segmentIndex: segmentIndex ?? null,
        segmentTotal: segmentTotal ?? null,
        baseLineId: baseLineId ?? null,
        engine,
        status: 'queued',
        errorMessage: null,
      },
      create: {
        taskId,
        clientId,
        bookId,
        lineId,
        chapterId: chapterId ?? null,
        speaker: speaker ?? null,
        lineType: lineType ?? null,
        emotion: (emotion ?? undefined) as any,
        isChapterHeader: isChapterHeader != null ? Boolean(isChapterHeader) : null,
        isSegment: isSegment != null ? Boolean(isSegment) : null,
        segmentIndex: segmentIndex ?? null,
        segmentTotal: segmentTotal ?? null,
        baseLineId: baseLineId ?? null,
        engine,
        status: 'queued',
      },
    });

    return { task };
  }

  async completeTask(taskId: string, payload: CompleteRenderTaskDto): Promise<TaskRegistryInternalResult> {
    const task = await this.prisma.renderTask.findUnique({ where: { taskId } });
    if (!task) throw new NotFoundException('RenderTask not found');

    const updated = await this.prisma.renderTask.update({
      where: { taskId },
      data: (() => {
        const data: Record<string, any> = {
        status: 'done',
        storageKey: payload.storageKey,
        durationMs: payload.durationMs != null ? Math.round(payload.durationMs) : null,
        errorMessage: null,
        };
        if (payload.chapterId !== undefined) {
          data.chapterId = payload.chapterId;
        }
        return data;
      })(),
    });

    return { task: updated };
  }

  async failTask(taskId: string, errorMessage: string): Promise<TaskRegistryInternalResult> {
    const task = await this.prisma.renderTask.findUnique({ where: { taskId } });
    if (!task) throw new NotFoundException('RenderTask not found');

    const updated = await this.prisma.renderTask.update({
      where: { taskId },
      data: {
        status: 'failed',
        errorMessage,
      },
    });

    return { task: updated };
  }

  async listTasks(params: { clientId: string; bookId: string }): Promise<{ tasks: RenderTask[] }> {
    const { clientId, bookId } = params;
    const tasks = await this.prisma.renderTask.findMany({
      where: { clientId, bookId },
      orderBy: { lineId: 'asc' },
    });
    return { tasks };
  }

  async upsertAssembly(payload: UpsertRenderAssemblyDto): Promise<TaskRegistryAssemblyResult> {
    const { assemblyId, clientId, bookId, type, chapterId, storageKey, durationMs } = payload;
    if (!assemblyId.trim()) throw new BadRequestException('assemblyId required');
    if (!clientId.trim() || !bookId.trim()) throw new BadRequestException('clientId/bookId required');
    if (!storageKey.trim()) throw new BadRequestException('storageKey required');
    const chapter = chapterId ?? 0;

    const assembly = await this.prisma.renderAssembly.upsert({
      where: { assemblyId },
      update: {
        storageKey,
        durationMs: durationMs ?? null,
        errorMessage: null,
        chapterId: chapter,
        type,
        clientId,
        bookId,
      },
      create: {
        assemblyId,
        clientId,
        bookId,
        type,
        chapterId: chapter,
        storageKey,
        durationMs: durationMs ?? null,
        errorMessage: null,
      },
    });

    return { assembly };
  }

  async getFinalAssembly(params: { clientId: string; bookId: string }): Promise<TaskRegistryAssemblyResult> {
    const assembly = await this.prisma.renderAssembly.findUnique({
      where: { clientId_bookId_type_chapterId: { clientId: params.clientId, bookId: params.bookId, type: 'book_final_wav', chapterId: 0 } },
    });
    if (!assembly) throw new NotFoundException('Final assembly not found');
    return { assembly };
  }

  async getChapterAssembly(params: { clientId: string; bookId: string; chapterId: number }): Promise<TaskRegistryAssemblyResult> {
    const assembly = await this.prisma.renderAssembly.findUnique({
      where: {
        clientId_bookId_type_chapterId: {
          clientId: params.clientId,
          bookId: params.bookId,
          type: 'book_chapter_wav',
          chapterId: params.chapterId,
        },
      },
    });
    if (!assembly) throw new NotFoundException('Chapter assembly not found');
    return { assembly };
  }
}

