import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class VoicesService {
  constructor(private readonly prisma: PrismaService) {}

  async list(filters: { language?: string; gender?: string; style?: string }) {
    return this.prisma.voice.findMany({
      where: {
        isActive: true,
        language: filters.language,
        gender: filters.gender as any,
        style: filters.style,
      },
      orderBy: [{ language: 'asc' }, { name: 'asc' }],
    });
  }

  async getById(id: string) {
    const v = await this.prisma.voice.findUnique({ where: { id } });
    if (!v || !v.isActive) throw new NotFoundException('Voice not found');
    return v;
  }
}

