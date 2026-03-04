import { Body, Controller, Delete, Get, Param, Patch, Post, Req, UseGuards } from '@nestjs/common';
import type { Project } from '@prisma/client';
import { AccessAuthGuard } from '../auth/guards';
import { ProjectsService } from './projects.service';
import { CreateProjectDto, UpdateProjectDto } from './dto';

@Controller('/api/projects')
export class ProjectsController {
  constructor(private readonly projects: ProjectsService) {}

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
    return { project: p };
  }

  @UseGuards(AccessAuthGuard)
  @Patch('/:id')
  async update(@Req() req: any, @Param('id') id: string, @Body() dto: UpdateProjectDto) {
    const p = await this.projects.update(id, req.user.sub, dto);
    return { project: p };
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
}

