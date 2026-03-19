import { Body, Controller, Get, Param, Patch, UseGuards } from '@nestjs/common';
import { AccessAuthGuard, AdminGuard } from '../auth/guards';
import { AdminService } from './admin.service';
import { AdminChangePasswordDto } from './dto';

@Controller('/api/admin')
@UseGuards(AccessAuthGuard, AdminGuard)
export class AdminController {
  constructor(private readonly admin: AdminService) {}

  @Get('/users')
  async listUsers() {
    return { users: await this.admin.listUsers() };
  }

  @Get('/users/:id')
  async getUser(@Param('id') id: string) {
    return { user: await this.admin.getUserDetail(id) };
  }

  @Patch('/users/:id/password')
  async changePassword(@Param('id') id: string, @Body() dto: AdminChangePasswordDto) {
    return this.admin.changeUserPassword(id, dto.newPassword);
  }

  @Get('/metrics')
  async getMetrics() {
    return this.admin.getMetrics();
  }
}
