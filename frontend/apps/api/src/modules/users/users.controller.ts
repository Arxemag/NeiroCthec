import { Body, Controller, Delete, Get, Param, Patch, Post, Req, UseGuards } from '@nestjs/common';
import { AccessAuthGuard } from '../auth/guards';
import { UsersService } from './users.service';
import { UserVoicesService } from './user-voices.service';
import { VoicesService } from '../voices/voices.service';
import { CreateUserVoiceDto, UpdateUserVoiceDto } from './user-voices.dto';

@Controller('/api/users')
export class UsersController {
  constructor(
    private readonly users: UsersService,
    private readonly userVoices: UserVoicesService,
    private readonly voices: VoicesService,
  ) {}

  @UseGuards(AccessAuthGuard)
  @Get('/me')
  async me(@Req() req: any) {
    return { user: await this.users.getById(req.user.sub) };
  }

  /**
   * DEV-эндпоинт: сделать текущего пользователя админом.
   * Легко вырезать: удалить этот метод и кнопку на фронте.
   */
  @UseGuards(AccessAuthGuard)
  @Post('/me/dev-become-admin')
  async devBecomeAdmin(@Req() req: any) {
    return { user: await this.users.makeAdmin(req.user.sub) };
  }

  /** Список своих голосов (метаданные: name, coreVoiceId). Файлы в Core. */
  @UseGuards(AccessAuthGuard)
  @Get('/me/voices')
  async listMyVoices(@Req() req: any) {
    const list = await this.userVoices.listByUser(req.user.sub);
    return {
      voices: list.map((v) => ({
        id: v.id,
        name: v.name,
        coreVoiceId: v.coreVoiceId,
        projectId: v.projectId ?? null,
        createdAt: v.createdAt.toISOString(),
      })),
    };
  }

  /** Добавить свой голос (метаданные; загрузка WAV в Core — отдельно, затем coreVoiceId сюда). */
  @UseGuards(AccessAuthGuard)
  @Post('/me/voices')
  async createMyVoice(@Req() req: any, @Body() dto: CreateUserVoiceDto) {
    const v = await this.userVoices.create(req.user.sub, dto);
    return {
      voice: {
        id: v.id,
        name: v.name,
        coreVoiceId: v.coreVoiceId,
        projectId: v.projectId ?? null,
        createdAt: v.createdAt.toISOString(),
      },
    };
  }

  @UseGuards(AccessAuthGuard)
  @Patch('/me/voices/:id')
  async updateMyVoice(@Req() req: any, @Param('id') id: string, @Body() dto: UpdateUserVoiceDto) {
    const v = await this.userVoices.update(id, req.user.sub, dto);
    return {
      voice: {
        id: v.id,
        name: v.name,
        coreVoiceId: v.coreVoiceId,
        projectId: v.projectId ?? null,
        createdAt: v.createdAt.toISOString(),
      },
    };
  }

  @UseGuards(AccessAuthGuard)
  @Delete('/me/voices/:id')
  async deleteMyVoice(@Req() req: any, @Param('id') id: string) {
    await this.userVoices.delete(id, req.user.sub);
    return { ok: true };
  }

  /** Прокси к Core: список доступных голосов (встроенные + свои по X-User-Id). */
  @UseGuards(AccessAuthGuard)
  @Get('/me/custom-voices')
  async listCustomVoicesFromCore(@Req() req: any) {
    const list = await this.voices.listFromCore(req.user.sub);
    return { voices: list };
  }
}

