import { Module } from '@nestjs/common';
import { AudiosController } from './audios.controller';
import { AudiosService } from './audios.service';

@Module({
  controllers: [AudiosController],
  providers: [AudiosService],
})
export class AudiosModule {}

