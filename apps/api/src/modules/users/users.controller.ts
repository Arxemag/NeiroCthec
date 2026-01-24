import { Controller, Get, Req, UseGuards } from '@nestjs/common';
import { AccessAuthGuard } from '../auth/guards';
import { UsersService } from './users.service';

@Controller('/api/users')
export class UsersController {
  constructor(private readonly users: UsersService) {}

  @UseGuards(AccessAuthGuard)
  @Get('/me')
  async me(@Req() req: any) {
    return { user: await this.users.getById(req.user.sub) };
  }
}

