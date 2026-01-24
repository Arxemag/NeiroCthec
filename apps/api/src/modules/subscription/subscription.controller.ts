import { Controller, Get, Post, Req, UseGuards } from '@nestjs/common';
import { AccessAuthGuard } from '../auth/guards';
import { SubscriptionService } from './subscription.service';

@Controller('/api/subscription')
export class SubscriptionController {
  constructor(private readonly subs: SubscriptionService) {}

  @UseGuards(AccessAuthGuard)
  @Get()
  async get(@Req() req: any) {
    return { subscription: await this.subs.getForUser(req.user.sub) };
  }

  @UseGuards(AccessAuthGuard)
  @Post('/upgrade')
  async upgrade(@Req() req: any) {
    return { subscription: await this.subs.upgradeStub(req.user.sub) };
  }
}

