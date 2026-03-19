import { Module } from '@nestjs/common';
import { UsersController } from './users.controller';
import { UsersService } from './users.service';
import { UserVoicesService } from './user-voices.service';
import { VoicesModule } from '../voices/voices.module';

@Module({
  imports: [VoicesModule],
  controllers: [UsersController],
  providers: [UsersService, UserVoicesService],
  exports: [UsersService, UserVoicesService],
})
export class UsersModule {}

