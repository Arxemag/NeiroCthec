import {
  BadRequestException,
  Body,
  Controller,
  Delete,
  ForbiddenException,
  Get,
  Headers,
  Param,
  Patch,
  Post,
  Req,
  Res,
  UploadedFile,
  UseGuards,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '../../lib/nestjs-platform-express';
import type { Response } from 'express';
// multer is a dependency of @nestjs/platform-express; use require to avoid missing types
const multer = require('multer') as { memoryStorage: () => unknown };
import { AccessAuthGuard } from '../auth/guards';
import { BooksService } from './books.service';
import { StorageService } from '../storage/storage.service';
import { CreateBookFromProjectDto, CreateSeriesDto, UpdateBookDto } from './dto';

const memoryStorage = multer.memoryStorage();

@Controller('/api/books')
export class BooksController {
  constructor(
    private readonly books: BooksService,
    private readonly storage: StorageService,
  ) {}

  @UseGuards(AccessAuthGuard)
  @Get()
  async list(@Req() req: any) {
    const items = await this.books.listByUser(req.user.sub);
    return { books: items, total: items.length };
  }

  @UseGuards(AccessAuthGuard)
  @Get('trash')
  async listTrash(@Req() req: any) {
    const items = await this.books.listTrashByUser(req.user.sub);
    return { books: items };
  }

  /** Вызов по расписанию (cron): безвозвратно удаляет книги из корзины старше 7 дней. Заголовок X-Cron-Secret должен совпадать с CRON_SECRET. */
  @Post('purge-trash')
  async purgeTrash(
    @Headers('x-cron-secret') cronSecret: string | undefined,
  ) {
    const expected = process.env.CRON_SECRET?.trim();
    if (!expected || cronSecret?.trim() !== expected) {
      throw new ForbiddenException('Forbidden');
    }
    const result = await this.books.purgeTrashOlderThanDays(7);
    return result;
  }

  @UseGuards(AccessAuthGuard)
  @Get('series')
  async listSeries(@Req() req: any) {
    const series = await this.books.listSeriesByUser(req.user.sub);
    return { series };
  }

  @UseGuards(AccessAuthGuard)
  @Post('series')
  async createSeries(@Req() req: any, @Body() dto: CreateSeriesDto) {
    const series = await this.books.createSeries(req.user.sub, dto.name);
    return { series };
  }

  @UseGuards(AccessAuthGuard)
  @Get(':id')
  async get(@Req() req: any, @Param('id') id: string) {
    const book = await this.books.getByIdForUser(id, req.user.sub);
    return { book };
  }

  @UseGuards(AccessAuthGuard)
  @Patch(':id')
  async update(@Req() req: any, @Param('id') id: string, @Body() dto: UpdateBookDto) {
    const book = await this.books.update(id, req.user.sub, dto);
    return { book };
  }

  @UseGuards(AccessAuthGuard)
  @Delete(':id')
  async delete(@Req() req: any, @Param('id') id: string) {
    await this.books.delete(id, req.user.sub);
    return { ok: true };
  }

  @UseGuards(AccessAuthGuard)
  @Post(':id/restore')
  async restore(@Req() req: any, @Param('id') id: string) {
    const book = await this.books.restore(id, req.user.sub);
    return { book };
  }

  @UseGuards(AccessAuthGuard)
  @Post(':id/cover')
  @UseInterceptors(FileInterceptor('file', { storage: memoryStorage, limits: { fileSize: 5 * 1024 * 1024 } }))
  async uploadCover(
    @Req() req: any,
    @Param('id') id: string,
    @UploadedFile() file: { buffer?: Buffer; mimetype?: string },
  ) {
    if (!file?.buffer) throw new BadRequestException('File required');
    const contentType = file.mimetype || 'image/jpeg';
    const { key } = await this.books.prepareCoverKey(id, req.user.sub, contentType);
    await this.storage.putObject({
      key,
      contentType,
      body: file.buffer,
    });
    await this.books.saveCoverStorageKey(id, req.user.sub, key);
    const book = await this.books.getByIdForUser(id, req.user.sub);
    return { book };
  }

  @UseGuards(AccessAuthGuard)
  @Get(':id/cover')
  async getCover(@Req() req: any, @Param('id') id: string, @Res() res: Response) {
    const key = await this.books.getCoverKey(id, req.user.sub);
    if (!key) {
      res.status(404).json({ message: 'Cover not found' });
      return;
    }
    const obj = await this.storage.getObjectStream({ key });
    res.setHeader('Content-Type', obj.contentType);
    if (obj.contentLength) res.setHeader('Content-Length', String(obj.contentLength));
    obj.body.pipe(res);
  }
}
