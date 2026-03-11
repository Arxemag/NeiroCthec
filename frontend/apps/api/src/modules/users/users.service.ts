import { Injectable } from '@nestjs/common';
import { UserRole } from '@prisma/client';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class UsersService {
  constructor(private readonly prisma: PrismaService) {}

  async getById(id: string) {
    return this.prisma.user.findUnique({
      where: { id },
      select: {
        id: true,
        email: true,
        role: true,
        subscriptionStatus: true,
        createdAt: true,
      },
    });
  }

  async makeAdmin(id: string) {
    return this.prisma.user.update({
      where: { id },
      data: { role: UserRole.admin },
      select: {
        id: true,
        email: true,
        role: true,
        subscriptionStatus: true,
        createdAt: true,
      },
    });
  }
}

