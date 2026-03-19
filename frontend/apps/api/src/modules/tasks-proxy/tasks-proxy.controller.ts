import { Controller, Get, Param, Res, Req, UseGuards } from '@nestjs/common';
import type { Request, Response } from 'express';
import { AccessAuthGuard } from '../auth/guards';
import { TasksProxyService } from './tasks-proxy.service';

@Controller('/api/tasks')
export class TasksProxyController {
  constructor(private readonly tasks: TasksProxyService) {}

  @UseGuards(AccessAuthGuard)
  @Get(':taskId')
  async getTask(
    @Req() req: Request & { user?: { sub?: string } },
    @Param('taskId') taskId: string,
  ) {
    const userId = req.user?.sub;
    if (!userId) return { taskId, status: 'forbidden' };
    return this.tasks.getTaskStatus(userId, taskId);
  }

  @UseGuards(AccessAuthGuard)
  @Get(':taskId/artifact')
  async getArtifact(
    @Req() req: Request & { user?: { sub?: string } },
    @Param('taskId') taskId: string,
    @Res() res: Response,
  ): Promise<void> {
    const userId = req.user?.sub;
    if (!userId) {
      res.status(403).json({ status: 'forbidden' });
      return;
    }
    await this.tasks.streamTaskArtifact(userId, taskId, res);
  }
}

