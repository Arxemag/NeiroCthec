import { Injectable } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';
import { JwtRefreshPayload } from './types';

function cookieExtractor(req: any): string | null {
  return req?.cookies?.refreshToken ?? null;
}

@Injectable()
export class JwtRefreshStrategy extends PassportStrategy(Strategy, 'jwt-refresh') {
  constructor() {
    super({
      jwtFromRequest: ExtractJwt.fromExtractors([cookieExtractor, ExtractJwt.fromAuthHeaderAsBearerToken()]),
      secretOrKey: process.env.JWT_REFRESH_SECRET,
    });
  }

  validate(payload: JwtRefreshPayload) {
    return payload;
  }
}

