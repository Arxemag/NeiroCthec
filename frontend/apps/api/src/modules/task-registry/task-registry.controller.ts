import { Body, Controller, Get, Headers, Param, ParseIntPipe, Post, Query } from '@nestjs/common';
import { TaskRegistryService } from './task-registry.service';
import { CreateRenderTaskDto, CompleteRenderTaskDto } from './dto';
import { UpsertRenderAssemblyDto } from './assembly.dto';

function requireInternalTokenOrAllow(headerToken: string | undefined): boolean {
  const required = process.env.TASK_REGISTRY_INTERNAL_TOKEN?.trim();
  if (!required) return true; // MVP: token disabled
  return typeof headerToken === 'string' && headerToken === required;
}

@Controller('/internal/task-registry')
export class TaskRegistryController {
  constructor(private readonly tasks: TaskRegistryService) {}

  @Get('/tasks/:taskId')
  async getOne(
    @Param('taskId') taskId: string,
    @Headers('X-Internal-Token') internalToken?: string,
  ) {
    if (!requireInternalTokenOrAllow(internalToken)) {
      return { status: 'forbidden' };
    }
    return this.tasks.getTask(taskId);
  }

  @Post('/tasks')
  async upsertTask(
    @Body() body: CreateRenderTaskDto,
    @Headers('X-Internal-Token') internalToken?: string,
  ) {
    if (!requireInternalTokenOrAllow(internalToken)) {
      return {
        status: 'forbidden',
      };
    }
    return this.tasks.upsertTask(body);
  }

  @Post('/tasks/:taskId/complete')
  async complete(
    @Param('taskId') taskId: string,
    @Body() body: CompleteRenderTaskDto,
    @Headers('X-Internal-Token') internalToken?: string,
  ) {
    if (!requireInternalTokenOrAllow(internalToken)) {
      return {
        status: 'forbidden',
      };
    }
    return this.tasks.completeTask(taskId, body);
  }

  @Post('/tasks/:taskId/fail')
  async fail(
    @Param('taskId') taskId: string,
    @Body() body: { errorMessage: string },
    @Headers('X-Internal-Token') internalToken?: string,
  ) {
    if (!requireInternalTokenOrAllow(internalToken)) {
      return { status: 'forbidden' };
    }
    return this.tasks.failTask(taskId, body?.errorMessage ?? 'failed');
  }

  @Get('/tasks')
  async list(
    @Query('clientId') clientId: string,
    @Query('bookId') bookId: string,
    @Headers('X-Internal-Token') internalToken?: string,
  ) {
    if (!requireInternalTokenOrAllow(internalToken)) {
      return { status: 'forbidden' };
    }
    return this.tasks.listTasks({ clientId, bookId });
  }

  @Post('/assemblies')
  async upsertAssembly(
    @Body() body: UpsertRenderAssemblyDto,
    @Headers('X-Internal-Token') internalToken?: string,
  ) {
    if (!requireInternalTokenOrAllow(internalToken)) {
      return { status: 'forbidden' };
    }
    return this.tasks.upsertAssembly(body);
  }

  @Get('/assemblies/final')
  async getFinal(
    @Query('clientId') clientId: string,
    @Query('bookId') bookId: string,
    @Headers('X-Internal-Token') internalToken?: string,
  ) {
    if (!requireInternalTokenOrAllow(internalToken)) {
      return { status: 'forbidden' };
    }
    return this.tasks.getFinalAssembly({ clientId, bookId });
  }

  @Get('/assemblies/chapter')
  async getChapter(
    @Query('clientId') clientId: string,
    @Query('bookId') bookId: string,
    @Query('chapterId', ParseIntPipe) chapterId: number,
    @Headers('X-Internal-Token') internalToken?: string,
  ) {
    if (!requireInternalTokenOrAllow(internalToken)) {
      return { status: 'forbidden' };
    }
    return this.tasks.getChapterAssembly({ clientId, bookId, chapterId });
  }
}

