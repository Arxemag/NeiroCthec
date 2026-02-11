import { CanActivate, ExecutionContext, ForbiddenException, Injectable } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';

export class AccessAuthGuard extends AuthGuard('jwt-access') {}
export class RefreshAuthGuard extends AuthGuard('jwt-refresh') {}

@Injectable()
export class AdminGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const req = context.switchToHttp().getRequest();
    const user = req.user;
    if (!user || user.role !== 'admin') throw new ForbiddenException('Admin only');
    return true;
  }
}

