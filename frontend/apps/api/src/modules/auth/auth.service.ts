import { BadRequestException, ForbiddenException, Injectable, UnauthorizedException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';
import * as argon2 from 'argon2';
import { JwtService } from '@nestjs/jwt';
import { nanoid } from 'nanoid';
import { JwtAccessPayload, JwtRefreshPayload } from './types';

function envNumber(name: string, fallback: number): number {
  const v = Number(process.env[name]);
  return Number.isFinite(v) && v > 0 ? v : fallback;
}

@Injectable()
export class AuthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly jwt: JwtService,
  ) {}

  async register(email: string, password: string) {
    const existing = await this.prisma.user.findUnique({ where: { email } });
    if (existing) throw new BadRequestException('Email already registered');

    const passwordHash = await argon2.hash(password);
    const user = await this.prisma.user.create({
      data: {
        email,
        passwordHash,
        subscription: { create: { status: 'free' } },
      },
    });

    return this.issueTokens(user.id);
  }

  async login(email: string, password: string) {
    const user = await this.prisma.user.findUnique({ where: { email } });
    if (!user) throw new UnauthorizedException('Invalid credentials');

    const ok = await argon2.verify(user.passwordHash, password);
    if (!ok) throw new UnauthorizedException('Invalid credentials');

    return this.issueTokens(user.id);
  }

  async logout(refreshTokenId: string) {
    await this.prisma.refreshToken.updateMany({
      where: { id: refreshTokenId },
      data: { revokedAt: new Date() },
    });
  }

  async setUserPassword(userId: string, newPassword: string) {
    const user = await this.prisma.user.findUnique({ where: { id: userId } });
    if (!user) throw new UnauthorizedException('User not found');
    const passwordHash = await argon2.hash(newPassword);
    await this.prisma.user.update({ where: { id: userId }, data: { passwordHash } });
  }

  async rotateRefreshToken(userId: string, refreshTokenId: string) {
    const token = await this.prisma.refreshToken.findFirst({
      where: { id: refreshTokenId, userId },
    });
    if (!token || token.revokedAt) throw new ForbiddenException('Refresh token revoked');
    if (token.expiresAt.getTime() < Date.now()) throw new ForbiddenException('Refresh token expired');

    await this.prisma.refreshToken.update({
      where: { id: refreshTokenId },
      data: { revokedAt: new Date() },
    });

    return this.issueTokens(userId);
  }

  async issueTokens(userId: string) {
    const user = await this.prisma.user.findUnique({ where: { id: userId } });
    if (!user) throw new UnauthorizedException();

    const accessTtl = envNumber('JWT_ACCESS_TTL_SECONDS', 900);
    const refreshTtl = envNumber('JWT_REFRESH_TTL_SECONDS', 30 * 24 * 3600);

    const accessPayload: JwtAccessPayload = {
      sub: user.id,
      email: user.email,
      role: user.role,
      subscriptionStatus: user.subscriptionStatus,
    };

    const refreshTokenId = nanoid(24);
    const refreshPayload: JwtRefreshPayload = { sub: user.id, tokenId: refreshTokenId };

    const accessToken = await this.jwt.signAsync(accessPayload, {
      secret: process.env.JWT_ACCESS_SECRET!,
      expiresIn: accessTtl,
    });

    const refreshToken = await this.jwt.signAsync(refreshPayload, {
      secret: process.env.JWT_REFRESH_SECRET!,
      expiresIn: refreshTtl,
    });

    // Store hashed refresh token id for revocation/auditing
    const tokenHash = await argon2.hash(refreshToken);
    await this.prisma.refreshToken.create({
      data: {
        id: refreshTokenId,
        userId: user.id,
        tokenHash,
        expiresAt: new Date(Date.now() + refreshTtl * 1000),
      },
    });

    return {
      user: {
        id: user.id,
        email: user.email,
        role: user.role,
        subscriptionStatus: user.subscriptionStatus,
      },
      accessToken,
      refreshToken,
      refreshTokenId,
      accessExpiresInSeconds: accessTtl,
      refreshExpiresInSeconds: refreshTtl,
    };
  }
}

