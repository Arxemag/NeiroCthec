import { ForbiddenException, Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import { ProjectsService } from '../projects/projects.service';
import type { Book, BookSeries } from '@prisma/client';
import type { UpdateBookDto } from './dto';

function toBookResponse(
  book: Book & { series?: BookSeries | null },
  basePath: string,
  appApiUrl?: string,
) {
  const hasAudio = Boolean(book.appBookId || book.audiobookFolder);
  return {
    id: book.id,
    projectId: book.appBookId ?? book.id,
    title: book.title,
    description: book.description,
    author: book.author,
    genre: book.genre,
    seriesId: book.seriesId,
    seriesName: book.series?.name ?? null,
    seriesOrder: book.seriesOrder,
    coverImageUrl: book.coverStorageKey ? `${basePath}/api/books/${book.id}/cover` : null,
    coverStorageKey: book.coverStorageKey,
    appBookId: book.appBookId,
    audiobookFolder: book.audiobookFolder ?? null,
    language: book.language,
    completedAt: book.completedAt?.toISOString(),
    updatedAt: book.updatedAt.toISOString(),
    audio: hasAudio
      ? { id: '', status: 'ready', streamUrl: '', format: null, durationSeconds: null }
      : null,
  };
}

@Injectable()
export class BooksService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly projects: ProjectsService,
  ) {}

  private getBasePath(): string {
    return process.env.NEXT_PUBLIC_API_BASE_URL ?? process.env.API_BASE_URL ?? 'http://localhost:4000';
  }

  async listByUser(userId: string) {
    const books = await this.prisma.book.findMany({
      where: { userId, deletedAt: null },
      orderBy: { updatedAt: 'desc' },
      include: { series: true },
    });
    const base = this.getBasePath();
    return books.map((b) => toBookResponse(b, base));
  }

  async getByIdForUser(bookId: string, userId: string) {
    const book = await this.prisma.book.findFirst({
      where: { id: bookId, userId },
      include: { series: true },
    });
    if (!book) throw new NotFoundException('Book not found');
    if (book.deletedAt) throw new NotFoundException('Book not found');
    return toBookResponse(book, this.getBasePath());
  }

  async update(bookId: string, userId: string, dto: UpdateBookDto) {
    const existing = await this.prisma.book.findFirst({
      where: { id: bookId, userId },
    });
    if (!existing) throw new NotFoundException('Book not found');
    if (existing.deletedAt) throw new NotFoundException('Book not found');

    const updated = await this.prisma.book.update({
      where: { id: bookId },
      data: {
        title: dto.title,
        description: dto.description ?? undefined,
        author: dto.author ?? undefined,
        genre: dto.genre ?? undefined,
        seriesId: dto.seriesId ?? undefined,
        seriesOrder: dto.seriesOrder ?? undefined,
      },
      include: { series: true },
    });
    return toBookResponse(updated, this.getBasePath());
  }

  async delete(bookId: string, userId: string) {
    const existing = await this.prisma.book.findFirst({
      where: { id: bookId, userId },
    });
    if (!existing) throw new NotFoundException('Book not found');
    if (existing.deletedAt) return;
    await this.prisma.book.update({
      where: { id: bookId },
      data: { deletedAt: new Date() },
    });
  }

  async listTrashByUser(userId: string) {
    const books = await this.prisma.book.findMany({
      where: { userId, deletedAt: { not: null } },
      orderBy: { deletedAt: 'desc' },
      select: { id: true, title: true, language: true, deletedAt: true },
    });
    return books.map((b) => ({
      id: b.id,
      title: b.title,
      language: b.language,
      deletedAt: b.deletedAt!.toISOString(),
    }));
  }

  async restore(bookId: string, userId: string) {
    const existing = await this.prisma.book.findFirst({
      where: { id: bookId, userId },
    });
    if (!existing) throw new NotFoundException('Book not found');
    if (!existing.deletedAt) return this.getByIdForUser(bookId, userId);
    const updated = await this.prisma.book.update({
      where: { id: bookId },
      data: { deletedAt: null },
      include: { series: true },
    });
    return toBookResponse(updated, this.getBasePath());
  }

  /**
   * Безвозвратно удаляет книги, находящиеся в корзине дольше указанного числа дней.
   * Вызывается по расписанию (cron). Восстановленная книга (deletedAt = null) не удаляется.
   */
  async purgeTrashOlderThanDays(days: number): Promise<{ deleted: number }> {
    const cutoff = new Date(Date.now() - days * 24 * 60 * 60 * 1000);
    const result = await this.prisma.book.deleteMany({
      where: { deletedAt: { not: null, lt: cutoff } },
    });
    return { deleted: result.count };
  }

  private getAppApiUrl(): string | undefined {
    const url = process.env.APP_API_URL ?? process.env.CORE_API_URL ?? '';
    return url.trim() || undefined;
  }

  async createFromProject(
    projectId: string,
    userId: string,
    body: { appBookId: string; appUserId?: string },
  ) {
    const project = await this.projects.getByIdForUser(projectId, userId);
    const appApiUrl = this.getAppApiUrl();
    /** В App API книга лежит по user_id из X-User-Id при загрузке (часто email), а не по Nest userId. */
    const appUserId = (body.appUserId ?? userId).trim() || userId;
    let audiobookFolder: string | undefined;
    if (appApiUrl) {
      const base = appApiUrl.replace(/\/$/, '');
      const res = await fetch(`${base}/internal/finalize-audiobook`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-Id': appUserId,
        },
        body: JSON.stringify({
          user_id: appUserId,
          book_id: body.appBookId,
          project_title: project.title,
        }),
      });
      if (!res.ok) {
        const text = await res.text();
        let detail = text;
        try {
          const j = JSON.parse(text) as { detail?: string };
          if (typeof j.detail === 'string') detail = j.detail;
        } catch {}
        throw new ForbiddenException(
          `Не удалось перенести аудиокнигу в хранилище: ${detail}`,
        );
      }
      const data = (await res.json()) as { folder?: string };
      audiobookFolder = typeof data.folder === 'string' ? data.folder : undefined;
    }
    const book = await this.prisma.book.create({
      data: {
        userId,
        title: project.title,
        language: project.language,
        appBookId: body.appBookId,
        audiobookFolder: audiobookFolder ?? undefined,
        completedAt: new Date(),
      },
      include: { series: true },
    });
    await this.projects.delete(projectId, userId);
    return toBookResponse(book, this.getBasePath());
  }

  async listSeriesByUser(userId: string) {
    const series = await this.prisma.bookSeries.findMany({
      where: { userId },
      orderBy: { name: 'asc' },
      include: {
        books: { where: { deletedAt: null }, select: { id: true } },
      },
    });
    return series.map((s) => ({
      id: s.id,
      name: s.name,
      bookCount: s.books.length,
    }));
  }

  async createSeries(userId: string, name: string) {
    const series = await this.prisma.bookSeries.create({
      data: { userId, name },
    });
    return { id: series.id, name: series.name };
  }

  async prepareCoverKey(bookId: string, userId: string, contentType: string) {
    const existing = await this.prisma.book.findFirst({
      where: { id: bookId, userId },
    });
    if (!existing) throw new NotFoundException('Book not found');
    if (existing.deletedAt) throw new NotFoundException('Book not found');

    const ext = contentType.includes('png') ? 'png' : contentType.includes('webp') ? 'webp' : 'jpg';
    const key = `books/${bookId}/cover.${ext}`;
    return { key };
  }

  async getCoverKey(bookId: string, userId: string): Promise<string | null> {
    const book = await this.prisma.book.findFirst({
      where: { id: bookId, userId },
      select: { coverStorageKey: true, deletedAt: true },
    });
    if (!book || book.deletedAt || !book.coverStorageKey) return null;
    return book.coverStorageKey;
  }

  async saveCoverStorageKey(bookId: string, userId: string, key: string) {
    const existing = await this.prisma.book.findFirst({
      where: { id: bookId, userId },
    });
    if (!existing) throw new NotFoundException('Book not found');
    await this.prisma.book.update({
      where: { id: bookId },
      data: { coverStorageKey: key },
    });
  }
}
