import { Body, Controller, Get, Post, Req, Res, UseGuards } from '@nestjs/common';
import { AuthService } from './auth.service';
import { LoginDto, RegisterDto } from './dto';
import { AccessAuthGuard, RefreshAuthGuard } from './guards';
import type { Response } from 'express';

function setRefreshCookie(res: Response, refreshToken: string) {
  res.cookie('refreshToken', refreshToken, {
    httpOnly: true,
    sameSite: 'lax',
    secure: process.env.NODE_ENV === 'production',
    path: '/api/auth',
  });
}

@Controller('/api/auth')
export class AuthController {
  constructor(private readonly auth: AuthService) {}

  @Post('/register')
  async register(@Body() dto: RegisterDto, @Res({ passthrough: true }) res: Response) {
    const tokens = await this.auth.register(dto.email, dto.password);
    setRefreshCookie(res, tokens.refreshToken);
    return tokens;
  }

  @Post('/login')
  async login(@Body() dto: LoginDto, @Res({ passthrough: true }) res: Response) {
    const tokens = await this.auth.login(dto.email, dto.password);
    setRefreshCookie(res, tokens.refreshToken);
    return tokens;
  }

  @UseGuards(AccessAuthGuard)
  @Get('/me')
  async me(@Req() req: any) {
    return { user: req.user };
  }

  @UseGuards(RefreshAuthGuard)
  @Post('/refresh')
  async refresh(@Req() req: any, @Res({ passthrough: true }) res: Response) {
    const { sub: userId, tokenId } = req.user;
    const tokens = await this.auth.rotateRefreshToken(userId, tokenId);
    setRefreshCookie(res, tokens.refreshToken);
    return tokens;
  }

  @UseGuards(RefreshAuthGuard)
  @Post('/logout')
  async logout(@Req() req: any, @Res({ passthrough: true }) res: Response) {
    const { tokenId } = req.user;
    await this.auth.logout(tokenId);
    res.clearCookie('refreshToken', { path: '/api/auth' });
    return { ok: true };
  }
}

