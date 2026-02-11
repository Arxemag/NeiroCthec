import { ConflictException, Injectable, NotFoundException } from '@nestjs/common';
import type { VoiceGender } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';
import type { UpdateVoiceDto } from './dto';

@Injectable()
export class VoicesService {
  constructor(private readonly prisma: PrismaService) {}

  async list(filters: { language?: string; gender?: string; style?: string }) {
    const where: { isActive: boolean; language?: string; gender?: VoiceGender; style?: string } = {
      isActive: true,
    };
    if (filters.language != null && filters.language !== '') where.language = filters.language;
    if (filters.gender != null && filters.gender !== '') where.gender = filters.gender as VoiceGender;
    if (filters.style != null && filters.style !== '') where.style = filters.style;

    return this.prisma.voice.findMany({
      where,
      orderBy: [{ language: 'asc' }, { name: 'asc' }],
    });
  }

  async getById(id: string) {
    const v = await this.prisma.voice.findUnique({ where: { id } });
    if (!v || !v.isActive) throw new NotFoundException('Voice not found');
    return v;
  }

  async update(id: string, dto: UpdateVoiceDto) {
    await this.getById(id);
    const data: { name?: string; characterDescription?: string | null } = {};
    if (dto.name != null) data.name = dto.name;
    if (dto.characterDescription !== undefined) data.characterDescription = dto.characterDescription;
    if (Object.keys(data).length === 0) return this.getById(id);
    return this.prisma.voice.update({
      where: { id },
      data,
    });
  }

  async delete(id: string) {
    await this.getById(id);
    const used = await this.prisma.projectVoice.count({ where: { voiceId: id } });
    if (used > 0) throw new ConflictException('Не удалось удалить: голос используется в проектах.');
    await this.prisma.voice.delete({ where: { id } });
  }
}

