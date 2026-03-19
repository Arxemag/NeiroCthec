import {
  BadRequestException,
  Body,
  Controller,
  Delete,
  Get,
  Param,
  Patch,
  Post,
  Req,
  UploadedFile,
  UseGuards,
  UseInterceptors,
} from '@nestjs/common';
import type { Project } from '@prisma/client';
import { FileInterceptor } from '../../lib/nestjs-platform-express';
import { AccessAuthGuard } from '../auth/guards';
import { ProjectsService } from './projects.service';
import { BooksService } from '../books/books.service';
import { UserVoicesService } from '../users/user-voices.service';
import { VoicesService } from '../voices/voices.service';
import { CreateProjectDto, UpdateProjectDto } from './dto';
import { CreateBookFromProjectDto } from '../books/dto';

const multer = require('multer') as { memoryStorage: () => unknown };
const memoryStorage = multer.memoryStorage();
const UPLOAD_TEXT_MAX_BYTES = 1 * 1024 * 1024; // 1 MB

@Controller('/api/projects')
export class ProjectsController {
  constructor(
    private readonly projects: ProjectsService,
    private readonly books: BooksService,
    private readonly userVoices: UserVoicesService,
    private readonly voices: VoicesService,
  ) {}

  @UseGuards(AccessAuthGuard)
  @Get()
  async list(@Req() req: any) {
    const projects = await this.projects.listByUser(req.user.sub);
    return {
      projects: projects.map((p: Project) => ({
        id: p.id,
        title: p.title,
        language: p.language,
        status: p.status,
        createdAt: p.createdAt,
        updatedAt: p.updatedAt,
      })),
    };
  }

  @UseGuards(AccessAuthGuard)
  @Get('trash')
  async listTrash(@Req() req: any) {
    const projects = await this.projects.listTrashByUser(req.user.sub);
    return {
      projects: projects.map((p: Pick<Project, 'id' | 'title' | 'language' | 'status' | 'deletedAt'>) => ({
        id: p.id,
        title: p.title,
        language: p.language,
        status: p.status,
        deletedAt: p.deletedAt,
      })),
    };
  }

  @UseGuards(AccessAuthGuard)
  @Post()
  async create(@Req() req: any, @Body() dto: CreateProjectDto) {
    const p = await this.projects.create(req.user.sub, dto);
    return { project: p };
  }

  @UseGuards(AccessAuthGuard)
  @Get('/:id')
  async get(@Req() req: any, @Param('id') id: string) {
    const p = await this.projects.getByIdForUser(id, req.user.sub);
    const voiceSettings = p.voiceSettings
      ? {
          narratorVoiceId: p.voiceSettings.narratorVoiceId ?? null,
          maleVoiceId: p.voiceSettings.maleVoiceId ?? null,
          femaleVoiceId: p.voiceSettings.femaleVoiceId ?? null,
        }
      : null;
    return {
      project: {
        ...p,
        voiceSettings,
      },
    };
  }

  /** Голоса пользователя + привязанные к проекту (для UI «Мои голоса» в контексте проекта). */
  @UseGuards(AccessAuthGuard)
  @Get(':id/voices')
  async getProjectVoices(@Req() req: any, @Param('id') id: string) {
    await this.projects.getByIdForUser(id, req.user.sub);
    const list = await this.userVoices.listForProject(req.user.sub, id);
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

  /** Прокси к Core: доступные голоса для проекта (X-User-Id, опционально project_id в Core). */
  @UseGuards(AccessAuthGuard)
  @Get(':id/available-voices')
  async getAvailableVoicesFromCore(@Req() req: any, @Param('id') id: string) {
    await this.projects.getByIdForUser(id, req.user.sub);
    const list = await this.voices.listFromCore(req.user.sub);
    return { voices: list };
  }

  @UseGuards(AccessAuthGuard)
  @Patch('/:id')
  async update(@Req() req: any, @Param('id') id: string, @Body() dto: UpdateProjectDto) {
    const patch: Parameters<ProjectsService['update']>[2] = {
      title: dto.title,
      text: dto.text,
      language: dto.language,
      voiceIds: dto.voiceIds,
      speakerSettings: dto.speakerSettings,
      voiceSettings: dto.voiceSettings,
    };
    const p = await this.projects.update(id, req.user.sub, patch);
    const voiceSettings = p.voiceSettings
      ? {
          narratorVoiceId: p.voiceSettings.narratorVoiceId ?? null,
          maleVoiceId: p.voiceSettings.maleVoiceId ?? null,
          femaleVoiceId: p.voiceSettings.femaleVoiceId ?? null,
        }
      : null;
    return { project: { ...p, voiceSettings } };
  }

  @UseGuards(AccessAuthGuard)
  @Delete('/:id')
  async delete(@Req() req: any, @Param('id') id: string) {
    await this.projects.delete(id, req.user.sub);
    return { ok: true };
  }

  @UseGuards(AccessAuthGuard)
  @Post(':id/restore')
  async restore(@Req() req: any, @Param('id') id: string) {
    const p = await this.projects.restore(id, req.user.sub);
    return { project: p };
  }

  @UseGuards(AccessAuthGuard)
  @Post(':id/create-book')
  async createBook(@Req() req: any, @Param('id') id: string, @Body() dto: CreateBookFromProjectDto) {
    const book = await this.books.createFromProject(id, req.user.sub, {
      appBookId: dto.appBookId,
      appUserId: dto.appUserId?.trim() || undefined,
    });
    return { bookId: book.id, book };
  }

  @UseGuards(AccessAuthGuard)
  @Post(':id/complete')
  async complete(@Req() req: any, @Param('id') id: string) {
    const project = await this.projects.complete(id, req.user.sub);
    return { project };
  }

  @UseGuards(AccessAuthGuard)
  @Get(':id/chapters')
  async chapters(@Req() req: any, @Param('id') id: string) {
    return this.projects.getChapters(id, req.user.sub);
  }

  @UseGuards(AccessAuthGuard)
  @Post(':id/preview-by-speakers')
  async previewBySpeakers(
    @Req() req: any,
    @Param('id') id: string,
    @Body() body: { bookId?: string } | undefined,
  ) {
    return this.projects.previewBySpeakers(id, req.user.sub, body);
  }

  @UseGuards(AccessAuthGuard)
  @Post(':id/upload-text')
  @UseInterceptors(
    FileInterceptor('file', {
      storage: memoryStorage,
      limits: { fileSize: UPLOAD_TEXT_MAX_BYTES },
    }),
  )
  async uploadText(
    @Req() req: any,
    @Param('id') id: string,
    @UploadedFile() file: { buffer?: Buffer; mimetype?: string },
  ) {
    if (!file?.buffer) throw new BadRequestException('File required');
    const text = file.buffer.toString('utf-8');
    if (!text.trim()) throw new BadRequestException('File is empty or not valid text');
    await this.projects.setText(id, req.user.sub, text);
    return { ok: true };
  }
}

